import os
import re
import subprocess
import tempfile
from typing import Optional
from debug import log


POWERSHELL_OCR_SCRIPT = r'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType=WindowsRuntime]

function Await-AsyncOperation {
    param(
        [Parameter(Mandatory=$true)] $Operation,
        [Parameter(Mandatory=$true)] [Type] $ResultType
    )

    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethodDefinition -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1

    $genericMethod = $method.MakeGenericMethod(@($ResultType))
    $task = $genericMethod.Invoke($null, @($Operation))
    return $task.GetAwaiter().GetResult()
}

$path = $env:TEXTCUT_OCR_IMAGE_PATH
$file = Await-AsyncOperation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = Await-AsyncOperation ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
$decoder = Await-AsyncOperation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await-AsyncOperation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { exit 3 }
$result = Await-AsyncOperation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ($null -eq $result -or $null -eq $result.Lines) { exit 0 }
$lines = @()
foreach ($line in $result.Lines) {
    $lines += $line.Text
}
Write-Output ($lines -join "`n")
'''


def _invert_bmp(bmp_bytes: bytes) -> bytes:
    if len(bmp_bytes) < 54:
        return bmp_bytes

    # Width at 18, Height at 22 (4 bytes each, little endian)
    width = int.from_bytes(bmp_bytes[18:22], "little")
    height = int.from_bytes(bmp_bytes[22:26], "little")

    # Standard BMP row padding: rows are aligned to 4 bytes
    row_size = ((24 * width + 31) // 32) * 4
    pixel_data = bytearray(bmp_bytes[54:])

    # Only invert the actual pixel data, leave padding alone
    for row in range(abs(height)):
        row_start = row * row_size
        row_end = row_start + (width * 3)
        if row_end > len(pixel_data):
            break
        for i in range(row_start, row_end):
            pixel_data[i] = 255 - pixel_data[i]

    return bytes(bmp_bytes[:54] + pixel_data)


def _score_text(text: str) -> int:
    if not text:
        return 0
    score = 0
    for char in text:
        if char.isalnum():
            score += 1
        elif char in " ，。！？：；\"'()[]{}<>":
            score += 0.1
    return score

def _normalize_ocr_text(text: str) -> str:
    cjk = r'\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af'
    cjk_punct = r'，。！？：；、「」『』（）〔〕【】《》〈〉、．・…—'
    ascii_punct = r',\.!\?:;\(\)\[\]\{\}<>'

    # Normalize line endings first.
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove spaces between adjacent CJK characters.
    text = re.sub(rf'([{cjk}])\s+([{cjk}])', r'\1\2', text)

    # Remove spaces between CJK and punctuation in both directions.
    text = re.sub(rf'([{cjk}])\s+([{cjk_punct}{ascii_punct}])', r'\1\2', text)
    text = re.sub(rf'([{cjk_punct}{ascii_punct}])\s+([{cjk}])', r'\1\2', text)

    # Collapse OCR-created spacing around hyphens/dashes between CJK fragments.
    text = re.sub(rf'([{cjk}])\s*[-—]+\s*([{cjk}])', r'\1-\2', text)

    # Remove spaces inside continuous CJK-heavy phrases iteratively.
    previous = None
    while previous != text:
        previous = text
        text = re.sub(rf'([{cjk}])\s+([{cjk}])', r'\1\2', text)
        text = re.sub(rf'([{cjk}])\s+([{cjk_punct}{ascii_punct}])', r'\1\2', text)
        text = re.sub(rf'([{cjk_punct}{ascii_punct}])\s+([{cjk}])', r'\1\2', text)

    # Normalize spaces per line while preserving line breaks.
    lines = []
    for line in text.split('\n'):
        line = re.sub(r'[ \t]+', ' ', line).strip()
        lines.append(line)

    # Keep non-empty lines and preserve their order.
    return '\n'.join(line for line in lines if line).strip()


def sync_run_ocr(image_bytes: bytes) -> Optional[str]:
    temp_path = None
    try:
        log(f"sync_run_ocr called with {len(image_bytes)} bytes")
        fd, temp_path = tempfile.mkstemp(suffix=".bmp", prefix="textcut_")
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(image_bytes)
        log(f"Wrote temp image file: {temp_path}")

        env = os.environ.copy()
        env["TEXTCUT_OCR_IMAGE_PATH"] = temp_path

        def run_powershell_ocr() -> str:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    POWERSHELL_OCR_SCRIPT,
                ],
                capture_output=True,
                text=False,
                timeout=30,
                env=env,
            )

            def decode_output(data: bytes) -> str:
                if not data:
                    return ""
                for encoding in ("utf-8-sig", "utf-8", "cp950", "cp936", "cp1252", "mbcs"):
                    try:
                        return data.decode(encoding).strip()
                    except Exception:
                        continue
                return data.decode("utf-8", errors="replace").strip()

            if result.returncode != 0:
                return ""
            return decode_output(result.stdout)

        # Pass 1: Original image
        text_orig = run_powershell_ocr()
        log(f"Original OCR result: {repr(text_orig)}")

        # Pass 2: Inverted image
        inverted_bytes = _invert_bmp(image_bytes)
        with open(temp_path, "wb") as f:
            f.write(inverted_bytes)
        text_inv = run_powershell_ocr()
        log(f"Inverted OCR result: {repr(text_inv)}")

        # Pick the best result based on content score
        score_orig = _score_text(text_orig)
        score_inv = _score_text(text_inv)
        log(f"Scores - Original: {score_orig}, Inverted: {score_inv}")

        if score_inv > score_orig:
            log("Choosing inverted variant as better result")
            best_text = text_inv
        else:
            log("Choosing original variant as better result")
            best_text = text_orig

        if not best_text:
            return None

        normalized_text = _normalize_ocr_text(best_text)
        log(f"Normalized OCR text: {repr(normalized_text)}")
        return normalized_text or None

    except Exception as e:
        log(f"OCR Error: {type(e).__name__}: {e}")
        print(f"OCR Error: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                log(f"Removed temp image file: {temp_path}")
            except Exception as cleanup_error:
                log(f"Failed to remove temp image file: {cleanup_error}")
