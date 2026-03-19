"""Action layer — singleton ActionBackend + backward-compatible module-level API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclaw.action.backend import ActionBackend

__all__ = ["click", "double_click", "scroll", "move_to", "type_text", "hotkey",
           "get_backend", "set_backend"]

_backend: ActionBackend | None = None


def get_backend() -> ActionBackend:
    """Return the active ActionBackend, creating a NativeActionBackend on first call."""
    global _backend
    if _backend is None:
        from xclaw.config import (
            HUMANIZE, BEZIER_DURATION_RANGE, BEZIER_STEPS, TYPE_DELAY_RANGE,
        )
        from xclaw.action.native_backend import NativeActionBackend

        if HUMANIZE:
            from xclaw.action.humanize_strategy import BezierStrategy
            strategy = BezierStrategy(
                duration_range=BEZIER_DURATION_RANGE,
                bezier_steps=BEZIER_STEPS,
                type_delay_range=TYPE_DELAY_RANGE,
            )
        else:
            from xclaw.action.humanize_strategy import NoopStrategy
            strategy = NoopStrategy()

        _backend = NativeActionBackend(humanize=strategy)
    return _backend


def set_backend(backend: ActionBackend) -> None:
    """Replace the active ActionBackend (e.g. with DryRunBackend for tests)."""
    global _backend
    _backend = backend


# -- Backward-compatible module-level functions ----------------------------

def click(x: int, y: int, button: str = "left"):
    return get_backend().click(x, y, button)


def double_click(x: int, y: int):
    return get_backend().double_click(x, y)


def scroll(direction: str, steps: int = 3):
    return get_backend().scroll(direction, steps)


def move_to(x: int, y: int):
    return get_backend().move_to(x, y)


def type_text(text: str):
    return get_backend().type_text(text)


def hotkey(combo: str):
    return get_backend().hotkey(combo)
