"""Click and scroll — delegates to ActionBackend."""

from xclaw.action import get_backend


def click(x: int, y: int, double: bool = False, button: str = "left") -> dict:
    """Click at the given screen coordinates.

    Returns:
        {"status": "ok", "action": "click"|"double_click", ...}
    """
    b = get_backend()
    return b.double_click(x, y) if double else b.click(x, y, button=button)


def scroll(direction: str, amount: int, x: int | None = None, y: int | None = None) -> dict:
    """Scroll the mouse wheel.

    Returns:
        {"status": "ok", "action": "scroll", ...}
    """
    return get_backend().scroll(direction, amount, x, y)


def drag(x1: int, y1: int, x2: int, y2: int, button: str = "left") -> dict:
    """Drag from (x1, y1) to (x2, y2).

    Returns:
        {"status": "ok", "action": "drag", ...}
    """
    return get_backend().drag(x1, y1, x2, y2, button=button)
