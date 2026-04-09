import tkinter as tk
from typing import Optional

class Clipboard:
    def __init__(self):
        # We need a hidden tkinter root to access the clipboard
        self.root = tk.Tk()
        self.root.withdraw()

    def copy(self, text: str) -> bool:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update() # Flush the clipboard
            return True
        except Exception as e:
            print(f"Clipboard Error: {e}")
            return False

    def destroy(self):
        self.root.destroy()

def copy_to_clipboard(text: str) -> bool:
    cb = Clipboard()
    success = cb.copy(text)
    cb.destroy()
    return success
