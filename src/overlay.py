import ctypes
import tkinter as tk
from ctypes import wintypes
from typing import List, Optional, Tuple
from config import OVERLAY_COLOR, OVERLAY_OPACITY, SELECTION_COLOR
from debug import log

user32 = ctypes.windll.user32

MIN_SELECTION_SIZE = 5
TINY_SELECTION_WARNING_SIZE = 20


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(RECT),
    wintypes.LPARAM,
)


class SelectionOverlay:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.overlays: List[tk.Toplevel] = []
        self.canvases: List[tk.Canvas] = []
        self.start_x = 0
        self.start_y = 0
        self.bbox: Optional[Tuple[int, int, int, int]] = None
        self.drag_canvas: Optional[tk.Canvas] = None
        self.rect_id = None
        self._callback_ref = None

    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        monitors = self._get_monitors()

        for monitor in monitors:
            overlay = tk.Toplevel(self.root)
            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", OVERLAY_OPACITY)
            overlay.configure(bg=OVERLAY_COLOR)
            overlay.overrideredirect(True)
            width = monitor[2] - monitor[0]
            height = monitor[3] - monitor[1]
            overlay.geometry(f"{width}x{height}{monitor[0]:+d}{monitor[1]:+d}")

            canvas = tk.Canvas(overlay, cursor="cross", bg=OVERLAY_COLOR, highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)

            overlay.bind("<ButtonPress-1>", self._on_button_press)
            overlay.bind("<B1-Motion>", self._on_mouse_drag)
            overlay.bind("<ButtonRelease-1>", self._on_button_release)
            overlay.bind("<Escape>", self._on_escape)

            overlay.update_idletasks()
            overlay.deiconify()
            overlay.lift()
            log(f"Overlay realized: rootx={overlay.winfo_rootx()}, rooty={overlay.winfo_rooty()}, width={overlay.winfo_width()}, height={overlay.winfo_height()}")
            self.overlays.append(overlay)
            self.canvases.append(canvas)

        if self.overlays:
            self.overlays[0].focus_force()
            self.canvases[0].focus_set()
            self.root.wait_window(self.overlays[0])

        return self.bbox

    def _get_monitors(self) -> List[Tuple[int, int, int, int]]:
        monitors: List[Tuple[int, int, int, int]] = []

        def callback(hmonitor, hdc, rect_ptr, lparam):
            rect = rect_ptr.contents
            log(f"Enumerating monitor: left={rect.left}, top={rect.top}, right={rect.right}, bottom={rect.bottom}")
            monitors.append((rect.left, rect.top, rect.right, rect.bottom))
            return True

        self._callback_ref = MonitorEnumProc(callback)
        user32.EnumDisplayMonitors(0, 0, self._callback_ref, 0)
        return monitors

    def _close(self):
        for overlay in self.overlays:
            if overlay.winfo_exists():
                overlay.destroy()
        self.overlays.clear()
        self.canvases.clear()
        self.drag_canvas = None
        self.rect_id = None

    def _find_canvas_for_widget(self, widget) -> Optional[tk.Canvas]:
        for canvas in self.canvases:
            if str(canvas) == str(widget):
                return canvas
        return None

    def _on_button_press(self, event):
        log(f"Mouse press: x_root={event.x_root}, y_root={event.y_root}, widget_rootx={event.widget.winfo_rootx()}, widget_rooty={event.widget.winfo_rooty()}")
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.drag_canvas = self._find_canvas_for_widget(event.widget)
        if self.drag_canvas is None:
            return
        if self.rect_id:
            self.drag_canvas.delete(self.rect_id)
        canvas_x = event.x_root - self.drag_canvas.winfo_rootx()
        canvas_y = event.y_root - self.drag_canvas.winfo_rooty()
        self.rect_id = self.drag_canvas.create_rectangle(
            canvas_x,
            canvas_y,
            canvas_x,
            canvas_y,
            outline=SELECTION_COLOR,
            width=2,
        )

    def _on_mouse_drag(self, event):
        if self.drag_canvas is None or self.rect_id is None:
            return
        start_canvas_x = self.start_x - self.drag_canvas.winfo_rootx()
        start_canvas_y = self.start_y - self.drag_canvas.winfo_rooty()
        current_canvas_x = event.x_root - self.drag_canvas.winfo_rootx()
        current_canvas_y = event.y_root - self.drag_canvas.winfo_rooty()
        self.drag_canvas.coords(
            self.rect_id,
            start_canvas_x,
            start_canvas_y,
            current_canvas_x,
            current_canvas_y,
        )

    def _on_button_release(self, event):
        log(f"Mouse release: x_root={event.x_root}, y_root={event.y_root}, widget_rootx={event.widget.winfo_rootx()}, widget_rooty={event.widget.winfo_rooty()}")
        end_x = event.x_root
        end_y = event.y_root
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        width = x2 - x1
        height = y2 - y1

        if width > MIN_SELECTION_SIZE and height > MIN_SELECTION_SIZE:
            if width <= TINY_SELECTION_WARNING_SIZE or height <= TINY_SELECTION_WARNING_SIZE:
                log(f"Tiny selection captured: width={width}, height={height}")
            self.bbox = (x1, y1, x2, y2)
        else:
            self.bbox = None
        self._close()

    def _on_escape(self, event):
        self.bbox = None
        self._close()
