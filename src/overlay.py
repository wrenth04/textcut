import ctypes
import tkinter as tk
from ctypes import wintypes
from typing import List, Optional, Tuple
from config import OVERLAY_COLOR, OVERLAY_OPACITY, SELECTION_COLOR
from debug import log

user32 = ctypes.windll.user32

# Configure Win32 API signatures for positioning (Windows only)
try:
    user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    user32.MoveWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
except Exception:
    pass

SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

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

    def _log_system_metrics(self):
        try:
            sm_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            sm_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            sm_cx = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            sm_cy = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            log(f"System metrics virtual screen: left={sm_x}, top={sm_y}, width={sm_cx}, height={sm_cy}")
        except Exception:
            pass

    def _log_tk_scaling(self):
        try:
            scaling = self.root.tk.call("tk", "scaling")
            fpix = self.root.winfo_fpixels("1i")
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            log(f"Tk scaling={scaling}, fpixels(1i)={fpix}, screen={sw}x{sh}")
        except Exception:
            pass

    def _move_window(self, hwnd: int, x: int, y: int, w: int, h: int):
        try:
            # MoveWindow uses physical pixels with the virtual screen origin.
            user32.MoveWindow(hwnd, x, y, w, h, True)
        except Exception:
            pass

    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        monitors = self._get_monitors()
        if not monitors:
            return None

        left = min(monitor[0] for monitor in monitors)
        top = min(monitor[1] for monitor in monitors)
        right = max(monitor[2] for monitor in monitors)
        bottom = max(monitor[3] for monitor in monitors)
        width = right - left
        height = bottom - top
        log(f"Virtual desktop bounds (EnumDisplayMonitors): left={left}, top={top}, right={right}, bottom={bottom}, width={width}, height={height}")
        self._log_system_metrics()
        self._log_tk_scaling()

        overlay = tk.Toplevel(self.root)
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", OVERLAY_OPACITY)
        overlay.configure(bg=OVERLAY_COLOR)
        overlay.overrideredirect(True)
        overlay.geometry(f"{width}x{height}{left:+d}{top:+d}")

        canvas = tk.Canvas(overlay, cursor="cross", bg=OVERLAY_COLOR, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        # Bind to the overlay window as well as the canvas to ensure events are captured
        for target in (overlay, canvas):
            target.bind("<ButtonPress-1>", self._on_button_press)
            target.bind("<B1-Motion>", self._on_mouse_drag)
            target.bind("<ButtonRelease-1>", self._on_button_release)
            target.bind("<Escape>", self._on_escape)

        overlay.update_idletasks()
        overlay.deiconify()
        overlay.lift()

        # Force overlay to the exact virtual desktop origin/size using SetWindowPos.
        try:
            hwnd = overlay.winfo_id()
            ok = user32.SetWindowPos(hwnd, 0, left, top, width, height, SWP_NOZORDER | SWP_NOACTIVATE)
            overlay.update_idletasks()
            if not ok:
                log(f"SetWindowPos failed for overlay HWND={hwnd}")
                self._close()
                return None
        except Exception as e:
            log(f"SetWindowPos exception: {e}")
            self._close()
            return None

        log(
            f"Overlay realized: rootx={overlay.winfo_rootx()}, rooty={overlay.winfo_rooty()}, "
            f"width={overlay.winfo_width()}, height={overlay.winfo_height()}"
        )
        self.overlays.append(overlay)
        self.canvases.append(canvas)

        overlay.focus_force()
        canvas.focus_set()
        self.root.wait_window(overlay)

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
        log(
            f"Mouse press: x_root={event.x_root}, y_root={event.y_root}, "
            f"widget_rootx={event.widget.winfo_rootx()}, widget_rooty={event.widget.winfo_rooty()}"
        )
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
        log(
            f"Mouse release: x_root={event.x_root}, y_root={event.y_root}, "
            f"widget_rootx={event.widget.winfo_rootx()}, widget_rooty={event.widget.winfo_rooty()}"
        )
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
