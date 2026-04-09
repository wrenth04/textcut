import os
import subprocess
import tempfile
from typing import Optional
from debug import log


POWERSHELL_OCR_SCRIPT = r'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]
$path = $args[0]
$file = [System.WindowsRuntimeSystemExtensions]::AsTask([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)).GetAwaiter().GetResult()
$stream = [System.WindowsRuntimeSystemExtensions]::AsTask($file.OpenReadAsync()).GetAwaiter().GetResult()
$decoder = [System.WindowsRuntimeSystemExtensions]::AsTask([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)).GetAwaiter().GetResult()
$bitmap = [System.WindowsRuntimeSystemExtensions]::AsTask($decoder.GetSoftwareBitmapAsync()).GetAwaiter().GetResult()
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { exit 3 }
$result = [System.WindowsRuntimeSystemExtensions]::AsTask($engine.RecognizeAsync($bitmap)).GetAwaiter().GetResult()
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output $result.Text
'''


def sync_run_ocr(image_bytes: bytes) -> Optional[str]:
    temp_path = None
    try:
        log(f"sync_run_ocr called with {len(image_bytes)} bytes")
        fd, temp_path = tempfile.mkstemp(suffix=".bmp", prefix="textcut_")
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(image_bytes)
        log(f"Wrote temp image file: {temp_path}")

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                POWERSHELL_OCR_SCRIPT,
                temp_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

        log(f"PowerShell OCR return code: {result.returncode}")
        if result.stderr:
            log(f"PowerShell OCR stderr: {result.stderr.strip()}")
        text = result.stdout.strip() if result.stdout else None
        log(f"PowerShell OCR stdout: {repr(text)}")

        if result.returncode != 0:
            return None
        return text or None
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
