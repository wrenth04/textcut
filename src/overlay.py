import tkinter as tk
from typing import Tuple, Optional
from config import OVERLAY_COLOR, OVERLAY_OPACITY, SELECTION_COLOR


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
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", OVERLAY_OPACITY)
        self.overlay.configure(bg=OVERLAY_COLOR)
        self.overlay.overrideredirect(True)

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
        self.rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline=SELECTION_COLOR, width=2)

    def _on_mouse_drag(self, event):
        if self.rect_id:
            start_canvas_x = self.canvas.canvasx(self.start_x - self.overlay.winfo_rootx())
            start_canvas_y = self.canvas.canvasy(self.start_y - self.overlay.winfo_rooty())
            self.canvas.coords(self.rect_id, start_canvas_x, start_canvas_y, event.x, event.y)

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
