import asyncio
from typing import Optional
import winrt.windows.media.ocr as ocr
import winrt.windows.graphics.imaging as imaging
from PIL import Image
import io

async def run_ocr(image: Image.Image) -> Optional[str]:
    """
    Uses Windows built-in OCR to recognize text from a PIL Image.
    """
    try:
        # Convert PIL Image to a format winrt can use (SoftwareBitmap)
        # Windows OCR requires a SoftwareBitmap.
        # The easiest path is saving to a stream and letting WinRT load it,
        # or using the winrt.windows.graphics.imaging APIs.

        # Save image to bytes buffer
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        # Create a random stream from bytes
        # Note: winrt.windows.storage.streams.DataWriter/DataReader can be used.
        # However, using the SoftwareBitmap.create_from_buffer is more direct
        # if we can get the raw pixels.

        # Alternative: Since we have the PIL image, let's use the SoftwareBitmap pixels.
        # SoftwareBitmap needs: width, height, pixels, bitmap_pixel_format
        width, height = image.size
        pixels = image.tobytes() # PIL RGB bytes

        # WinRT SoftwareBitmap.create_from_buffer requires a buffer
        # We'll use a simpler approach: using the winrt.windows.graphics.imaging.BitmapDecoder
        # to load the image from the bytes stream.

        # This is a bit verbose in Python WinRT.
        # Let's try the simpler WinRT OCR flow.

        # For the sake of a robust implementation in Python, we usually
        # wrap the async calls in a loop.

        # 1. Get OCR engine
        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            return None

        # 2. We need a SoftwareBitmap.
        # The most reliable way to create one from PIL is via a stream:
        # (This requires winrt.windows.storage.streams.InMemoryRandomAccessStream)
        from winrt.windows.storage.streams import InMemoryRandomAccessStream

        stream = InMemoryRandomAccessStream()
        writer = winrt.windows.storage.streams.DataWriter()
        writer.write_bytes(img_bytes)
        await writer.store_async(stream)
        stream.seek(0)

        decoder = await imaging.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        # 3. Recognize text
        result = await engine.recognize_async(bitmap)

        # 4. Aggregate text lines
        lines = [line.text for line in result.lines]
        return "\n".join(lines) if lines else None

    except Exception as e:
        print(f"OCR Error: {e}")
        return None

def sync_run_ocr(image: Image.Image) -> Optional[str]:
    """Synchronous wrapper for the async run_ocr."""
    return asyncio.run(run_ocr(image))
