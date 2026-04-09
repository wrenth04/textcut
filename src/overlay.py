import ctypes
import tkinter as tk
from typing import Tuple, Optional
from config import OVERLAY_COLOR, OVERLAY_OPACITY, SELECTION_COLOR

user32 = ctypes.windll.user32
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class SelectionOverlay:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.overlay = None
        self.canvas = None
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.bbox = None

    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        virtual_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        virtual_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        virtual_width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        virtual_height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", OVERLAY_OPACITY)
        self.overlay.configure(bg=OVERLAY_COLOR)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{virtual_width}x{virtual_height}{virtual_x:+d}{virtual_y:+d}")

        self.canvas = tk.Canvas(self.overlay, cursor="cross", bg=OVERLAY_COLOR, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay.bind("<ButtonPress-1>", self._on_button_press)
        self.overlay.bind("<B1-Motion>", self._on_mouse_drag)
        self.overlay.bind("<ButtonRelease-1>", self._on_button_release)
        self.overlay.bind("<Escape>", self._on_escape)

        self.overlay.update_idletasks()
        self.overlay.deiconify()
        self.overlay.lift()
        self.overlay.focus_force()
        self.canvas.focus_set()
        self.root.wait_window(self.overlay)
        return self.bbox

    def _close(self):
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()

    def _on_button_press(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        canvas_x = event.x_root - self.overlay.winfo_rootx()
        canvas_y = event.y_root - self.overlay.winfo_rooty()
        self.rect_id = self.canvas.create_rectangle(canvas_x, canvas_y, canvas_x, canvas_y, outline=SELECTION_COLOR, width=2)

    def _on_mouse_drag(self, event):
        if self.rect_id:
            start_canvas_x = self.start_x - self.overlay.winfo_rootx()
            start_canvas_y = self.start_y - self.overlay.winfo_rooty()
            current_canvas_x = event.x_root - self.overlay.winfo_rootx()
            current_canvas_y = event.y_root - self.overlay.winfo_rooty()
            self.canvas.coords(self.rect_id, start_canvas_x, start_canvas_y, current_canvas_x, current_canvas_y)

    def _on_button_release(self, event):
        end_x = event.x_root
        end_y = event.y_root
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 > 5 and y2 - y1 > 5:
            self.bbox = (x1, y1, x2, y2)
        else:
            self.bbox = None
        self._close()

    def _on_escape(self, event):
        self.bbox = None
        self._close()
