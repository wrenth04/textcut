import ctypes
from ctypes import wintypes
from typing import Tuple
from debug import log

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def _build_bmp_bytes(width: int, height: int, pixel_data: bytes) -> bytes:
    row_size = ((24 * width + 31) // 32) * 4
    image_size = row_size * height
    file_header_size = 14
    info_header_size = 40
    offset = file_header_size + info_header_size
    file_size = offset + image_size

    file_header = bytearray()
    file_header.extend(b"BM")
    file_header.extend(file_size.to_bytes(4, "little"))
    file_header.extend((0).to_bytes(2, "little"))
    file_header.extend((0).to_bytes(2, "little"))
    file_header.extend(offset.to_bytes(4, "little"))

    info_header = bytearray()
    info_header.extend(info_header_size.to_bytes(4, "little"))
    info_header.extend(width.to_bytes(4, "little", signed=True))
    info_header.extend(height.to_bytes(4, "little", signed=True))
    info_header.extend((1).to_bytes(2, "little"))
    info_header.extend((24).to_bytes(2, "little"))
    info_header.extend((0).to_bytes(4, "little"))
    info_header.extend(image_size.to_bytes(4, "little"))
    info_header.extend((0).to_bytes(4, "little", signed=True))
    info_header.extend((0).to_bytes(4, "little", signed=True))
    info_header.extend((0).to_bytes(4, "little"))
    info_header.extend((0).to_bytes(4, "little"))

    return bytes(file_header + info_header) + pixel_data


def capture_region(bbox: Tuple[int, int, int, int]) -> bytes:
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    log(f"capture_region called with bbox={bbox}, width={width}, height={height}")

    if width <= 0 or height <= 0:
        raise ValueError("Invalid capture region")

    screen_dc = user32.GetDC(0)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)

    try:
        if not gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, x1, y1, SRCCOPY):
            raise RuntimeError("BitBlt failed")

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 24
        bmi.bmiHeader.biCompression = BI_RGB

        row_size = ((24 * width + 31) // 32) * 4
        buffer_size = row_size * height
        buffer = ctypes.create_string_buffer(buffer_size)

        scan_lines = gdi32.GetDIBits(
            mem_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
        )
        if scan_lines != height:
            raise RuntimeError("GetDIBits failed")

        return _build_bmp_bytes(width, height, buffer.raw)
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, screen_dc)
