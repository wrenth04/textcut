import os
import re
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple
from capture import capture_region
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

DEFAULT_UPSCALE_FACTORS = [3]
SMALL_TEXT_UPSCALE_FACTORS = [3, 4, 5]
SMALL_SELECTION_WIDTH = 160
SMALL_SELECTION_HEIGHT = 80
SMALL_SELECTION_AREA = 20000
LOW_CONFIDENCE_SCORE = 3


OCRResult = Dict[str, Optional[str]]


def _parse_bmp_dimensions(bmp_bytes: bytes) -> Tuple[int, int]:
    if len(bmp_bytes) < 54:
        raise ValueError("Invalid BMP data")
    width = int.from_bytes(bmp_bytes[18:22], "little", signed=True)
    height = int.from_bytes(bmp_bytes[22:26], "little", signed=True)
    return abs(width), abs(height)


def _get_bmp_row_size(width: int) -> int:
    return ((24 * width + 31) // 32) * 4


def _invert_bmp(bmp_bytes: bytes) -> bytes:
    if len(bmp_bytes) < 54:
        return bmp_bytes

    width, height = _parse_bmp_dimensions(bmp_bytes)
    row_size = _get_bmp_row_size(width)
    pixel_data = bytearray(bmp_bytes[54:])

    for row in range(height):
        row_start = row * row_size
        row_end = row_start + (width * 3)
        if row_end > len(pixel_data):
            break
        for i in range(row_start, row_end):
            pixel_data[i] = 255 - pixel_data[i]

    return bytes(bmp_bytes[:54] + pixel_data)


def _high_contrast_bmp(bmp_bytes: bytes, threshold: int = 180) -> bytes:
    if len(bmp_bytes) < 54:
        return bmp_bytes

    width, height = _parse_bmp_dimensions(bmp_bytes)
    row_size = _get_bmp_row_size(width)
    pixel_data = bytearray(bmp_bytes[54:])

    for row in range(height):
        row_start = row * row_size
        row_end = row_start + (width * 3)
        if row_end > len(pixel_data):
            break
        for i in range(row_start, row_end, 3):
            b = pixel_data[i]
            g = pixel_data[i + 1]
            r = pixel_data[i + 2]
            gray = (r * 30 + g * 59 + b * 11) // 100
            value = 255 if gray >= threshold else 0
            pixel_data[i] = value
            pixel_data[i + 1] = value
            pixel_data[i + 2] = value

    return bytes(bmp_bytes[:54] + pixel_data)


def _score_text(text: str) -> float:
    if not text:
        return 0

    score = 0.0
    for char in text:
        if char.isalnum():
            score += 1.0
        elif char in " ，。！？：；\"'()[]{}<>":
            score += 0.2
        elif char.isspace():
            score += 0.05
        else:
            score -= 0.15

    stripped = text.strip()
    if len(stripped) >= 4:
        score += min(len(stripped) * 0.1, 2.0)
    if re.search(r"[A-Za-z0-9\u4e00-\u9fff]", stripped):
        score += 1.0
    return score


def _normalize_ocr_text(text: str) -> str:
    cjk = r'\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af'
    cjk_punct = r'，。！？：；、「」『』（）〔〕【】《》〈〉、．・…—'
    ascii_punct = r',\.!\?:;\(\)\[\]\{\}<>'

    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(rf'([{cjk}])\s+([{cjk}])', r'\1\2', text)
    text = re.sub(rf'([{cjk}])\s+([{cjk_punct}{ascii_punct}])', r'\1\2', text)
    text = re.sub(rf'([{cjk_punct}{ascii_punct}])\s+([{cjk}])', r'\1\2', text)
    text = re.sub(rf'([{cjk}])\s*[-—]+\s*([{cjk}])', r'\1-\2', text)

    previous = None
    while previous != text:
        previous = text
        text = re.sub(rf'([{cjk}])\s+([{cjk}])', r'\1\2', text)
        text = re.sub(rf'([{cjk}])\s+([{cjk_punct}{ascii_punct}])', r'\1\2', text)
        text = re.sub(rf'([{cjk_punct}{ascii_punct}])\s+([{cjk}])', r'\1\2', text)

    lines = []
    for line in text.split('\n'):
        line = re.sub(r'[ \t]+', ' ', line).strip()
        lines.append(line)

    return '\n'.join(line for line in lines if line).strip()


def _is_small_selection(bbox: Tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    return (
        width <= SMALL_SELECTION_WIDTH
        or height <= SMALL_SELECTION_HEIGHT
        or width * height <= SMALL_SELECTION_AREA
    )


def _variant_specs_for_bbox(bbox: Tuple[int, int, int, int]) -> List[Tuple[int, str]]:
    factors = SMALL_TEXT_UPSCALE_FACTORS if _is_small_selection(bbox) else DEFAULT_UPSCALE_FACTORS
    specs: List[Tuple[int, str]] = []
    for factor in factors:
        specs.append((factor, "original"))
        specs.append((factor, "inverted"))
        if _is_small_selection(bbox):
            specs.append((factor, "high_contrast"))
    return specs


def _prepare_variant(bbox: Tuple[int, int, int, int], upscale_factor: int, variant: str) -> bytes:
    bmp_bytes = capture_region(bbox, upscale_factor=upscale_factor)
    if variant == "original":
        return bmp_bytes
    if variant == "inverted":
        return _invert_bmp(bmp_bytes)
    if variant == "high_contrast":
        return _high_contrast_bmp(bmp_bytes)
    raise ValueError(f"Unsupported OCR variant: {variant}")


def _run_powershell_ocr(image_bytes: bytes) -> str:
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".bmp", prefix="textcut_")
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(image_bytes)

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

        if result.returncode != 0:
            stderr = decode_output(result.stderr)
            log(f"PowerShell OCR failed with code {result.returncode}: {stderr}")
            return ""
        return decode_output(result.stdout)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_error:
                log(f"Failed to remove temp image file: {cleanup_error}")


def sync_run_ocr(bbox: Tuple[int, int, int, int]) -> OCRResult:
    try:
        log(f"sync_run_ocr called with bbox={bbox}")
        best_text = ""
        best_score = 0.0
        best_variant = None

        for upscale_factor, variant in _variant_specs_for_bbox(bbox):
            image_bytes = _prepare_variant(bbox, upscale_factor, variant)
            width, height = _parse_bmp_dimensions(image_bytes)
            log(f"Running OCR variant={variant}, factor={upscale_factor}, size={width}x{height}")
            text = _run_powershell_ocr(image_bytes)
            score = _score_text(text)
            log(f"OCR variant={variant}, factor={upscale_factor}, score={score}, text={repr(text)}")
            if score > best_score:
                best_score = score
                best_text = text
                best_variant = f"{variant}@{upscale_factor}x"

        normalized_text = _normalize_ocr_text(best_text) if best_text else ""
        if normalized_text:
            log(f"Best OCR result chosen from {best_variant}: {repr(normalized_text)}")
            return {"status": "success", "text": normalized_text}

        status = "low_confidence" if _is_small_selection(bbox) or best_score > 0 else "no_text"
        log(f"OCR finished without reliable text. status={status}, best_score={best_score}, variant={best_variant}")
        return {"status": status, "text": None}
    except Exception as e:
        log(f"OCR Error: {type(e).__name__}: {e}")
        print(f"OCR Error: {e}")
        return {"status": "error", "text": None}
