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

        stdout_text = decode_output(result.stdout)
        stderr_text = decode_output(result.stderr)

        log(f"PowerShell OCR return code: {result.returncode}")
        if stderr_text:
            log(f"PowerShell OCR stderr: {stderr_text}")
        text = stdout_text or None
        log(f"PowerShell OCR stdout: {repr(text)}")

        if result.returncode != 0:
            return None
        if not text:
            return None

        normalized_text = _normalize_ocr_text(text)
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
