"""Humanization strategies — decouple human-like delays from platform backends."""

from __future__ import annotations

import random
import time
from typing import Callable, Protocol, runtime_checkable

from xclaw.action.humanize import bezier_point


@runtime_checkable
class HumanizeStrategy(Protocol):
    """Controls human-like timing injected by NativeActionBackend."""

    def move_to_target(self, x: int, y: int, move_fn: Callable[[int, int], None]) -> tuple[int, int]:
        """Move cursor to (x, y) using *move_fn*, return final coords."""
        ...

    def pre_click_delay(self) -> None: ...
    def inter_click_delay(self) -> None: ...
    def pre_key_delay(self) -> None: ...
    def type_char_delay(self) -> None: ...

    def scroll_chunk(self, remaining: int) -> int:
        """Return how many scroll units to consume from *remaining*."""
        ...

    def inter_scroll_delay(self) -> None: ...
    def pre_drag_delay(self) -> None: ...


class NoopStrategy:
    """No humanization — direct operation."""

    def move_to_target(self, x: int, y: int, move_fn: Callable[[int, int], None]) -> tuple[int, int]:
        move_fn(x, y)
        return x, y

    def pre_click_delay(self) -> None:
        pass

    def inter_click_delay(self) -> None:
        pass

    def pre_key_delay(self) -> None:
        pass

    def type_char_delay(self) -> None:
        pass

    def scroll_chunk(self, remaining: int) -> int:
        return remaining

    def inter_scroll_delay(self) -> None:
        pass

    def pre_drag_delay(self) -> None:
        pass


def _get_cursor_pos() -> tuple[int, int]:
    from xclaw.action.mouse_win32 import _cursor_pos
    return _cursor_pos()


class BezierStrategy:
    """Bezier curve movement + jitter + random delays."""

    def __init__(
        self,
        duration_range: tuple[float, float] = (0.3, 0.8),
        bezier_steps: int = 30,
        click_jitter: int = 2,
        scroll_jitter: int = 5,
        type_delay_range: tuple[float, float] = (0.05, 0.15),
        pre_click_delay_range: tuple[float, float] = (0.02, 0.06),
        key_delay_range: tuple[float, float] = (0.03, 0.12),
    ):
        self.duration_range = duration_range
        self.bezier_steps = bezier_steps
        self.click_jitter = click_jitter
        self.scroll_jitter = scroll_jitter
        self.type_delay_range = type_delay_range
        self.pre_click_delay_range = pre_click_delay_range
        self.key_delay_range = key_delay_range

    def _bezier_move(self, sx: int, sy: int, ex: int, ey: int, move_fn: Callable[[int, int], None]):
        dx = ex - sx
        dy = ey - sy
        cp1 = (
            sx + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
            sy + dy * random.uniform(0.0, 0.3) + random.uniform(-50, 50),
        )
        cp2 = (
            sx + dx * random.uniform(0.6, 0.8) + random.uniform(-50, 50),
            sy + dy * random.uniform(0.7, 1.0) + random.uniform(-50, 50),
        )
        duration = random.uniform(*self.duration_range)
        t0 = time.perf_counter()
        for i in range(1, self.bezier_steps + 1):
            t = i / self.bezier_steps
            t = t * t * (3 - 2 * t)  # ease-in-out
            px, py = bezier_point(t, (sx, sy), cp1, cp2, (ex, ey))
            move_fn(int(px), int(py))
            # T0-relative sleep: absorbs accumulated timing error
            target = t0 + (i / self.bezier_steps) * duration
            remaining = target - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

    def move_to_target(self, x: int, y: int, move_fn: Callable[[int, int], None]) -> tuple[int, int]:
        sx, sy = _get_cursor_pos()
        self._bezier_move(sx, sy, x, y, move_fn)
        jx = x + random.randint(-self.click_jitter, self.click_jitter)
        jy = y + random.randint(-self.click_jitter, self.click_jitter)
        move_fn(jx, jy)
        return jx, jy

    def pre_click_delay(self) -> None:
        time.sleep(random.uniform(*self.pre_click_delay_range))

    def inter_click_delay(self) -> None:
        time.sleep(random.uniform(0.05, 0.10))

    def pre_key_delay(self) -> None:
        time.sleep(random.uniform(*self.key_delay_range))

    def type_char_delay(self) -> None:
        time.sleep(random.uniform(*self.type_delay_range))

    def scroll_chunk(self, remaining: int) -> int:
        chunk_min = max(1, remaining // 5)
        chunk_max = max(2, remaining // 2)
        return min(remaining, random.randint(chunk_min, chunk_max))

    def inter_scroll_delay(self) -> None:
        time.sleep(random.uniform(0.02, 0.08))

    def pre_drag_delay(self) -> None:
        time.sleep(random.uniform(0.04, 0.10))
