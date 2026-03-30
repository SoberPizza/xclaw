"""Action layer — singleton ActionBackend + backward-compatible module-level API."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclaw.action.backend import ActionBackend

__all__ = ["click", "double_click", "scroll", "move_to", "drag",
           "type_text", "hotkey",
           "get_backend", "set_backend", "freeze_backend"]

_backend: ActionBackend | None = None
_lock = threading.Lock()
_frozen = False


def _create_default_backend() -> ActionBackend:
    """Create the default NativeActionBackend with humanize config."""
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

    return NativeActionBackend(humanize=strategy)


def get_backend() -> ActionBackend:
    """Return the active ActionBackend, creating a NativeActionBackend on first call."""
    global _backend
    with _lock:
        if _backend is None:
            _backend = _create_default_backend()
        return _backend


def set_backend(backend: ActionBackend) -> None:
    """Replace the active ActionBackend (e.g. with DryRunBackend for tests).

    Raises RuntimeError if ``freeze_backend()`` has been called.
    """
    global _backend
    with _lock:
        if _frozen:
            raise RuntimeError(
                "ActionBackend is frozen after freeze_backend(). "
                "Call set_backend() before any freeze."
            )
        _backend = backend


def freeze_backend() -> None:
    """Prevent further ``set_backend()`` calls.

    Call this after initialization in production to guard against runtime
    backend replacement.  Does NOT affect ``get_backend()``.
    """
    global _frozen
    with _lock:
        _frozen = True


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


def drag(x1: int, y1: int, x2: int, y2: int, button: str = "left"):
    return get_backend().drag(x1, y1, x2, y2, button=button)
