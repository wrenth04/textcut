import mss
from PIL import Image
from typing import Tuple

def capture_region(bbox: Tuple[int, int, int, int]) -> Image.Image:
    """
    Captures the screen region specified by bbox (x1, y1, x2, y2)
    and returns a PIL Image.
    """
    x1, y1, x2, y2 = bbox

    # mss expects monitor = {'top': y, 'left': x, 'width': w, 'height': h}
    monitor = {
        "top": y1,
        "left": x1,
        "width": x2 - x1,
        "height": y2 - y1,
    }

    with mss.mss() as sct:
        # Grab the screen region
        screenshot = sct.grab(monitor)
        # Convert to PIL Image
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
