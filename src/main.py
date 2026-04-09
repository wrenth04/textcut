import sys
import time
from .hotkey import start_hotkey_listener
from .overlay import SelectionOverlay
from .capture import capture_region
from .ocr import sync_run_ocr
from .clipboard import copy_to_clipboard
import tkinter as tk
from tkinter import messagebox

def on_hotkey_pressed():
    print("Hotkey pressed! Activating selection overlay...")

    # 1. Select Region
    overlay = SelectionOverlay()
    bbox = overlay.get_selection()

    if bbox is None:
        print("Selection cancelled.")
        return

    print(f"Region selected: {bbox}")

    # 2. Capture Region
    try:
        image = capture_region(bbox)
    except Exception as e:
        print(f"Capture failed: {e}")
        return

    # 3. OCR Image
    print("Running OCR...")
    text = sync_run_ocr(image)

    if text:
        print(f"OCR Result:\n{text}")
        # 4. Copy to Clipboard
        if copy_to_clipboard(text):
            print("Text copied to clipboard.")
            # Optional: show a brief toast/notification
            # Using a simple tkinter window for now
            show_toast("Success", "Text copied to clipboard!")
        else:
            print("Failed to copy to clipboard.")
    else:
        print("No text recognized.")
        show_toast("OCR Result", "No text found in selected region.")

def show_toast(title, message):
    # Simple transient notification
    root = tk.Tk()
    root.withdraw()
    # Toplevel for toast
    toast = tk.Toplevel(root)
    toast.title(title)
    toast.geometry("250x100+500+400") # Simple fixed position
    toast.attributes("-topmost", True)

    label = tk.Label(toast, text=message, pady=20)
    label.pack()

    # Auto-destroy after 2 seconds
    toast.after(2000, toast.destroy)
    root.after(2100, root.destroy)
    root.mainloop()

def main():
    print("TextCut started. Press Ctrl+Shift+Alt+S to capture text.")

    # Start global hotkey listener
    listener = start_hotkey_listener(on_hotkey_pressed)

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down TextCut...")
        listener.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
