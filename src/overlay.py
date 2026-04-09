import tkinter as tk
from typing import Tuple, Optional
from .config import OVERLAY_COLOR, OVERLAY_OPACITY, SELECTION_COLOR

class SelectionOverlay:
    def __init__(self):
        self.root = None
        self.canvas = None
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.bbox = None  # (x1, y1, x2, y2)

    def get_selection(self) -> Optional[Tuple[int, int, int, int]]:
        self.root = tk.Tk()
        self.root.withdraw() # Hide main window

        # Create a fullscreen, topmost, transparent-ish window
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", OVERLAY_OPACITY)
        self.overlay.configure(bg=OVERLAY_COLOR)
        self.overlay.overrideredirect(True) # Remove window decorations

        # Make the window "click-through" if possible, but we need events.
        # On Windows, we can't easily do "semi-transparent and click-through"
        # while capturing drags without a proper window.
        # For now, the alpha overlay will capture all events.

        self.canvas = tk.Canvas(
            self.overlay,
            cursor="cross",
            bg=OVERLAY_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay.bind("<ButtonPress-1>", self._on_button_press)
        self.overlay.bind("<B1-Motion>", self._on_mouse_drag)
        self.overlay.bind("<ButtonRelease-1>", self._on_button_release)
        self.overlay.bind("<Escape>", self._on_escape)

        # Center window to capture events
        self.overlay.focus_force()

        self.root.mainloop()

        res = self.bbox
        self.root.destroy()
        return res

    def _on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline=SELECTION_COLOR, width=2
        )

    def _on_mouse_drag(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def _on_button_release(self, event):
        end_x, end_y = event.x, event.y
        # Normalize coordinates (ensure x1 < x2 and y1 < y2)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 > 5 and y2 - y1 > 5: # Minimum selection size
            self.bbox = (x1, y1, x2, y2)
            self.root.quit() # Exit mainloop
        else:
            # Selection too small, keep overlay open or cancel?
            # Let's just keep it open.
            pass

    def _on_escape(self, event):
        self.bbox = None
        self.root.quit()
