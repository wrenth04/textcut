import queue
import threading
import tkinter as tk
import ctypes
from hotkey import start_hotkey_listener
from overlay import SelectionOverlay
from ocr import sync_run_ocr
from clipboard import copy_to_clipboard
from debug import log

def initialize_dpi_awareness():
    """
    Initialize Windows DPI awareness to ensure coordinates from Tkinter
    and Win32 GDI match physical screen pixels.
    """
    if ctypes.windll.shell32:
        try:
            # Try modern Per-Monitor DPI Awareness V2 (Windows 10 1703+)
            # PER_MONITOR_AWARE_V2 = 2
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(2) != 0:
                log("DPI Awareness: SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2) succeeded")
                return True
        except Exception:
            pass

        try:
            # Fallback to Per-Monitor DPI Awareness (Windows 8.1+)
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            if ctypes.windll.user32.SetProcessDpiAwareness(2) != 0:
                log("DPI Awareness: SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE) succeeded")
                return True
        except Exception:
            pass

        try:
            # Fallback to System DPI Awareness (Windows XP+)
            if ctypes.windll.user32.SetProcessDPIAware() != 0:
                log("DPI Awareness: SetProcessDPIAware() succeeded")
                return True
        except Exception:
            pass

    log("DPI Awareness: Failed to set DPI awareness or not on Windows")
    return False

class TextCutApp:
    def __init__(self):
        initialize_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()
        self.event_queue = queue.Queue()
        self.is_busy = False
        self.listener = start_hotkey_listener(self._on_hotkey_pressed, self._on_hotkey_status)
        self.root.after(50, self._poll_hotkey_events)

    def _on_hotkey_pressed(self):
        log("Hotkey event received")
        self.event_queue.put("capture")

    def _on_hotkey_status(self, status):
        log(f"Hotkey status: {status}")
        self.event_queue.put(status)

    def _poll_hotkey_events(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                if event == "capture":
                    self.show_toast("TextCut", "Hotkey detected")
                    self.handle_capture()
                elif event == "hotkey_registered":
                    self.show_toast("TextCut", "Hotkey registered: Alt+C")
                elif isinstance(event, str) and event.startswith("hotkey_error:"):
                    error_code = event.split(":", 1)[1]
                    self.show_toast("TextCut Error", f"Hotkey registration failed: {error_code}")
                elif isinstance(event, tuple) and event[0] == "ocr_done":
                    self._handle_ocr_result(event[1])
                elif isinstance(event, tuple) and event[0] == "ocr_error":
                    self._handle_ocr_error(event[1])
        except queue.Empty:
            pass
        self.root.after(50, self._poll_hotkey_events)

    def handle_capture(self):
        if self.is_busy:
            log("Capture ignored because app is busy")
            return
        self.is_busy = True
        log("Capture started")
        try:
            overlay = SelectionOverlay(self.root)
            bbox = overlay.get_selection()
            log(f"Selection result: {bbox}")
            if bbox is None:
                self.is_busy = False
                return

            self.show_toast("TextCut", "Running OCR...")
            threading.Thread(target=self._run_ocr_worker, args=(bbox,), daemon=True).start()
        except Exception as e:
            log(f"Capture error: {e}")
            self.show_toast("Error", str(e))
            self.is_busy = False
            log("Capture finished")

    def _run_ocr_worker(self, bbox):
        try:
            log("OCR worker started")
            result = sync_run_ocr(bbox)
            text = result["text"]
            log(f"OCR worker finished with length: {0 if not text else len(text)}")
            self.event_queue.put(("ocr_done", result))
        except Exception as e:
            log(f"OCR worker error: {e}")
            self.event_queue.put(("ocr_error", str(e)))

    def _handle_ocr_result(self, result):
        try:
            self.show_toast("TextCut", "OCR finished")
            text = result["text"]
            status = result["status"]
            if text:
                if copy_to_clipboard(self.root, text):
                    log("Clipboard copy succeeded")
                    self.show_toast("Success", "Text copied to clipboard!")
                else:
                    log("Clipboard copy failed")
                    self.show_toast("Error", "Failed to copy text to clipboard.")
            elif status == "low_confidence":
                self.show_toast("OCR Result", "Text may be too small or unclear. Try selecting a slightly larger area.")
            else:
                self.show_toast("OCR Result", "No text found. Try selecting a larger area or bigger text.")
        finally:
            self.is_busy = False
            log("Capture finished")

    def _handle_ocr_error(self, error_message):
        self.show_toast("Error", error_message)
        self.is_busy = False
        log("Capture finished")

    def show_toast(self, title, message):
        log(f"Toast: {title} - {message}")
        toast = tk.Toplevel(self.root)
        toast.title(title)
        toast.geometry("320x120+500+400")
        toast.attributes("-topmost", True)
        label = tk.Label(toast, text=message, pady=20, wraplength=280)
        label.pack()
        toast.after(2500, toast.destroy)

    def run(self):
        log("Application started")
        try:
            self.root.mainloop()
        finally:
            log("Application stopping")
            self.listener.stop()
            self.root.destroy()


def main():
    app = TextCutApp()
    app.run()


if __name__ == "__main__":
    main()
