"""Click and scroll — delegates to ActionBackend."""

from xclaw.action import get_backend


def click(x: int, y: int, double: bool = False) -> dict:
    """Click at the given screen coordinates.

    Returns:
        {"status": "ok", "action": "click"|"double_click", ...}
    """
    b = get_backend()
    return b.double_click(x, y) if double else b.click(x, y)


def scroll(direction: str, amount: int, x: int | None = None, y: int | None = None) -> dict:
    """Scroll the mouse wheel.

    Returns:
        {"status": "ok", "action": "scroll", ...}
    """
    return get_backend().scroll(direction, amount, x, y)
