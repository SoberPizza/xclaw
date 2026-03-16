import time

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


def scroll(direction: str, amount: int, x: int | None = None, y: int | None = None) -> dict:
    """Scroll the mouse wheel.

    Args:
        direction: 'up' or 'down'.
        amount: Number of scroll units.
        x: Optional X coordinate to move mouse before scrolling.
        y: Optional Y coordinate to move mouse before scrolling.

    Returns:
        {"status": "ok", "action": "scroll", "direction": direction, "amount": amount, "x": x, "y": y}
    """
    # If coordinates not specified, default to screen center
    if x is None or y is None:
        x = pyautogui.size().width // 2
        y = pyautogui.size().height // 2

    # Move mouse to specified position
    pyautogui.moveTo(x, y)
    time.sleep(0.1)  # Wait for mouse movement to complete

    # Execute scroll
    scroll_amount = amount if direction == "up" else -amount
    pyautogui.scroll(scroll_amount)

    return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount, "x": x, "y": y}
