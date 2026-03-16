import pyautogui

from xclaw.config import HUMANIZE


def click(x: int, y: int, double: bool = False) -> dict:
    """Click at the given screen coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        double: If True, double-click.

    Returns:
        {"status": "ok", "action": "click", "x": x, "y": y, "double": double}
    """
    if HUMANIZE:
        from xclaw.action.humanize import humanized_click
        humanized_click(x, y, double=double)
    else:
        clicks = 2 if double else 1
        pyautogui.click(x, y, clicks=clicks)
    return {"status": "ok", "action": "click", "x": x, "y": y, "double": double}


def scroll(direction: str, amount: int) -> dict:
    """Scroll the mouse wheel.

    Args:
        direction: 'up' or 'down'.
        amount: Number of scroll units.

    Returns:
        {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}
    """
    scroll_amount = amount if direction == "up" else -amount
    pyautogui.scroll(scroll_amount)
    return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}
