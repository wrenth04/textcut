import ctypes
from ctypes import wintypes
from typing import Tuple
from debug import log

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
COLORONCOLOR = 3
UPSCALE_FACTOR = 3


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

    scaled_width = width * UPSCALE_FACTOR
    scaled_height = height * UPSCALE_FACTOR
    log(f"Upscaling capture to {scaled_width}x{scaled_height}")

    screen_dc = user32.GetDC(0)
    src_dc = gdi32.CreateCompatibleDC(screen_dc)
    dst_dc = gdi32.CreateCompatibleDC(screen_dc)
    src_bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    dst_bitmap = gdi32.CreateCompatibleBitmap(screen_dc, scaled_width, scaled_height)
    old_src_obj = gdi32.SelectObject(src_dc, src_bitmap)
    old_dst_obj = gdi32.SelectObject(dst_dc, dst_bitmap)

    try:
        if not gdi32.BitBlt(src_dc, 0, 0, width, height, screen_dc, x1, y1, SRCCOPY):
            raise RuntimeError("BitBlt failed")

        gdi32.SetStretchBltMode(dst_dc, COLORONCOLOR)
        if not gdi32.StretchBlt(dst_dc, 0, 0, scaled_width, scaled_height, src_dc, 0, 0, width, height, SRCCOPY):
            raise RuntimeError("StretchBlt failed")

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = scaled_width
        bmi.bmiHeader.biHeight = scaled_height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 24
        bmi.bmiHeader.biCompression = BI_RGB

        row_size = ((24 * scaled_width + 31) // 32) * 4
        buffer_size = row_size * scaled_height
        buffer = ctypes.create_string_buffer(buffer_size)

        scan_lines = gdi32.GetDIBits(
            dst_dc,
            dst_bitmap,
            0,
            scaled_height,
            buffer,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
        )
        if scan_lines != scaled_height:
            raise RuntimeError("GetDIBits failed")

        return _build_bmp_bytes(scaled_width, scaled_height, buffer.raw)
    finally:
        gdi32.SelectObject(src_dc, old_src_obj)
        gdi32.SelectObject(dst_dc, old_dst_obj)
        gdi32.DeleteObject(src_bitmap)
        gdi32.DeleteObject(dst_bitmap)
        gdi32.DeleteDC(src_dc)
        gdi32.DeleteDC(dst_dc)
        user32.ReleaseDC(0, screen_dc)
