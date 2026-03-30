"""Type text and press keys — delegates to ActionBackend."""

from xclaw.action import get_backend


def type_text(text: str) -> dict:
    """Type text at the current cursor position.

    Returns:
        {"status": "ok", "action": "type", "text": text}
    """
    return get_backend().type_text(text)


def press_key(key: str) -> dict:
    """Press a single key or key combination.

    Returns:
        {"status": "ok", "action": "press", "key": key}
    """
    return get_backend().press_key(key)


def hotkey(combo: str) -> dict:
    """Execute a key combination (e.g. ctrl+c, alt+f4).

    Returns:
        {"status": "ok", "action": "hotkey", "combo": combo}
    """
    get_backend().hotkey(combo)
    return {"status": "ok", "action": "hotkey", "combo": combo}
