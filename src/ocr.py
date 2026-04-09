import asyncio
from typing import Optional
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream


async def run_ocr(image_bytes: bytes) -> Optional[str]:
    """Uses Windows built-in OCR to recognize text from image bytes."""
    try:
        engine = OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            return None

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(image_bytes)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        return result.text.strip() if result.text else None
    except Exception as e:
        print(f"OCR Error: {e}")
        return None


def sync_run_ocr(image_bytes: bytes) -> Optional[str]:
    """Synchronous wrapper for the async run_ocr."""
    return asyncio.run(run_ocr(image_bytes))
