# Configuration for TextCut
import ctypes

# Global Hotkey Configuration
# MOD_ALT = 0x0001, MOD_CONTROL = 0x0002, MOD_SHIFT = 0x0004, MOD_WIN = 0x0008
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Example: Alt + C
HOTKEY_MODIFIERS = MOD_ALT
HOTKEY_VK = 0x43  # 'C' key

# Overlay Configuration
OVERLAY_COLOR = "#000000"  # Black
OVERLAY_OPACITY = 0.3      # 30% opacity
SELECTION_COLOR = "#00FF00" # Green border for selection

# Application Constants
APP_NAME = "TextCut"
