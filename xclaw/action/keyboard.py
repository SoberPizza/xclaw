import pyautogui

from xclaw.config import HUMANIZE


def type_text(text: str) -> dict:
    """Type text at the current cursor position.

    Args:
        text: The text to type.

    Returns:
        {"status": "ok", "action": "type", "text": text}
    """
    if HUMANIZE:
        from xclaw.action.humanize import humanized_type
        humanized_type(text)
    else:
        try:
            text.encode("ascii")
            pyautogui.write(text, interval=0.02)
        except UnicodeEncodeError:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")

    return {"status": "ok", "action": "type", "text": text}


def press_key(key: str) -> dict:
    """Press a single key.

    Args:
        key: Key name (e.g. 'enter', 'tab', 'escape', 'backspace').

    Returns:
        {"status": "ok", "action": "press", "key": key}
    """
    pyautogui.press(key)
    return {"status": "ok", "action": "press", "key": key}
