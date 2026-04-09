import ctypes
import ctypes.wintypes
import threading
from typing import Callable, Optional
from config import HOTKEY_MODIFIERS, HOTKEY_VK

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


class HotkeyListener(threading.Thread):
    def __init__(self, callback: Callable[[], None], status_callback: Optional[Callable[[str], None]] = None):
        super().__init__(daemon=True)
        self.callback = callback
        self.status_callback = status_callback
        self._stop_event = threading.Event()
        self.hotkey_id = 1
        self.thread_id = None

    def _notify(self, message: str):
        if self.status_callback:
            self.status_callback(message)

    def run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, self.hotkey_id, HOTKEY_MODIFIERS, HOTKEY_VK):
            error_code = ctypes.GetLastError()
            self._notify(f"hotkey_error:{error_code}")
            return

        self._notify("hotkey_registered")
        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or msg.message == WM_QUIT:
                break
            if msg.message == WM_HOTKEY:
                self.callback()

        user32.UnregisterHotKey(None, self.hotkey_id)

    def stop(self):
        self._stop_event.set()
        if self.thread_id is not None:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


def start_hotkey_listener(callback: Callable[[], None], status_callback: Optional[Callable[[str], None]] = None) -> HotkeyListener:
    listener = HotkeyListener(callback, status_callback)
    listener.start()
    return listener
