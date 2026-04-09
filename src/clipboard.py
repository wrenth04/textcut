def copy_to_clipboard(root, text: str) -> bool:
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        return True
    except Exception as e:
        print(f"Clipboard Error: {e}")
        return False
