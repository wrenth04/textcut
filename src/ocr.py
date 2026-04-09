import asyncio
import ctypes
import os
import tempfile
from typing import Optional
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage import StorageFile
from debug import log


async def run_ocr(image_bytes: bytes) -> Optional[str]:
    """Uses Windows built-in OCR to recognize text from image bytes."""
    temp_path = None
    try:
        log(f"run_ocr called with {len(image_bytes)} bytes")
        log("Creating OcrEngine")
        engine = OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            log("OcrEngine.try_create_from_user_profile_languages returned None")
            return None

        fd, temp_path = tempfile.mkstemp(suffix=".bmp", prefix="textcut_")
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(image_bytes)
        log(f"Wrote temp image file: {temp_path}")

        log("Awaiting StorageFile.get_file_from_path_async")
        storage_file = await StorageFile.get_file_from_path_async(temp_path)

        log("Awaiting storage_file.open_read_async")
        stream = await storage_file.open_read_async()

        log("Awaiting BitmapDecoder.create_async")
        decoder = await BitmapDecoder.create_async(stream)

        log("Awaiting decoder.get_software_bitmap_async")
        bitmap = await decoder.get_software_bitmap_async()

        log("Awaiting engine.recognize_async")
        result = await engine.recognize_async(bitmap)

        text = result.text.strip() if result.text else None
        log(f"OCR raw result: {repr(text)}")
        return text
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


def sync_run_ocr(image_bytes: bytes) -> Optional[str]:
    """Synchronous wrapper for the async run_ocr."""
    ole32 = ctypes.windll.ole32
    COINIT_APARTMENTTHREADED = 0x2
    init_result = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    log(f"CoInitializeEx result: {init_result}")
    try:
        return asyncio.run(run_ocr(image_bytes))
    finally:
        if init_result in (0, 1):
            ole32.CoUninitialize()
