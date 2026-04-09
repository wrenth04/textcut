import ctypes
import threading
from typing import Callable
from .config import HOTKEY_MODIFIERS, HOTKEY_VK

user32 = ctypes.windll.user32

class HotkeyListener(threading.Thread):
    def __init__(self, callback: Callable[[], None]):
        super().__init__(daemon=True)
        self.callback = callback
        self._stop_event = threading.Event()
        self.hotkey_id = 1

    def run(self):
        # Register the global hotkey
        if not user32.RegisterHotKey(None, self.hotkey_id, HOTKEY_MODIFIERS, HOTKEY_VK):
            raise RuntimeError(f"Failed to register hotkey: {HOTKEY_MODIFIERS} + {hex(HOTKEY_VK)}")

        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            # PeekMessage or GetMessage. GetMessage blocks, which is fine for a daemon thread.
            # We use a small timeout or similar if we needed to poll,
            # but RegisterHotKey sends WM_HOTKEY to the thread's message queue.
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312:  # WM_HOTKEY
                    self.callback()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

    def stop(self):
        self._stop_event.set()
        user32.UnregisterHotKey(None, self.hotkey_id)
        # Post a dummy message to wake up GetMessageW
        user32.PostQuitMessage(0)

def start_hotkey_listener(callback: Callable[[], None]) -> HotkeyListener:
    listener = HotkeyListener(callback)
    listener.start()
    return listener
