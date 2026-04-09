import os
from datetime import datetime

LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "textcut.log")
DEBUG_ENABLED = os.environ.get("TEXTCUT_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def log(message: str):
    if not DEBUG_ENABLED:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
