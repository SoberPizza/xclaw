"""Humanization strategies — decouple human-like delays from platform backends."""

from __future__ import annotations

import math
import random
import time
from typing import Callable, Protocol, runtime_checkable

from xclaw.action.humanize import asymmetric_ease, bezier_point, lognormal_delay


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
    """Human-realistic mouse movement and timing.

    Mouse paths follow cubic Bezier curves with:
    - Fitts' Law distance-adaptive duration
    - Dynamic step count (simulating ~125 Hz mouse polling)
    - Distance-proportional control-point noise
    - Asymmetric ease-in-out (longer deceleration phase)
    - Probabilistic overshoot + correction on long moves
    - Gaussian micro-tremor on intermediate points

    All timing delays use lognormal distributions (matching real human
    reaction-time statistics) instead of uniform distributions.
    """

    def __init__(
        self,
        duration_range: tuple[float, float] = (0.3, 0.8),
        click_jitter: int = 2,
        scroll_jitter: int = 5,
        type_delay_range: tuple[float, float] = (0.05, 0.15),
        pre_click_delay_range: tuple[float, float] = (0.02, 0.06),
        key_delay_range: tuple[float, float] = (0.03, 0.12),
        polling_rate_range: tuple[float, float] = (100, 130),
        overshoot_probability: float = 0.25,
        overshoot_min_distance: float = 80,
    ):
        self.duration_range = duration_range
        self.click_jitter = click_jitter
        self.scroll_jitter = scroll_jitter
        self.type_delay_range = type_delay_range
        self.pre_click_delay_range = pre_click_delay_range
        self.key_delay_range = key_delay_range
        self.polling_rate_range = polling_rate_range
        self.overshoot_probability = overshoot_probability
        self.overshoot_min_distance = overshoot_min_distance

    # ── Fitts' Law duration ────────────────────────────────────────────

    def _fitts_duration(self, distance: float) -> float:
        """Compute a Fitts' Law-based movement duration with lognormal noise."""
        if distance < 1:
            return 0.02
        base = 0.12 + 0.10 * math.log2(1 + distance / 15)
        return lognormal_delay(base, sigma=0.2, lo=0.06, hi=1.5)

    # ── Core Bezier move ───────────────────────────────────────────────

    def _bezier_move(
        self, sx: int, sy: int, ex: int, ey: int,
        move_fn: Callable[[int, int], None],
    ):
        dx = ex - sx
        dy = ey - sy
        distance = math.hypot(dx, dy)

        # Duration adapts to distance (Fitts' Law)
        duration = self._fitts_duration(distance)

        # Step count from simulated mouse polling rate
        polling_rate = random.uniform(*self.polling_rate_range)
        steps = max(8, int(duration * polling_rate))

        # Control-point noise scales with distance
        noise = max(3, min(80, distance * random.uniform(0.05, 0.20)))
        cp1 = (
            sx + dx * random.uniform(0.2, 0.4) + random.uniform(-noise, noise),
            sy + dy * random.uniform(0.0, 0.3) + random.uniform(-noise, noise),
        )
        cp2 = (
            sx + dx * random.uniform(0.6, 0.8) + random.uniform(-noise, noise),
            sy + dy * random.uniform(0.7, 1.0) + random.uniform(-noise, noise),
        )

        t0 = time.perf_counter()
        for i in range(1, steps + 1):
            t = i / steps
            # Asymmetric ease: fast acceleration, slow deceleration
            t = asymmetric_ease(t)
            px, py = bezier_point(t, (sx, sy), cp1, cp2, (ex, ey))

            # Micro-tremor on intermediate points (not start/end region)
            frac = i / steps
            if 0.1 < frac < 0.9:
                px += random.gauss(0, 0.5)
                py += random.gauss(0, 0.5)

            move_fn(int(px), int(py))

            # T0-relative sleep: absorbs accumulated timing error
            target = t0 + (i / steps) * duration
            remaining = target - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

    # ── Overshoot + correction ─────────────────────────────────────────

    def _maybe_overshoot(
        self, x: int, y: int, sx: int, sy: int,
        move_fn: Callable[[int, int], None],
    ) -> tuple[int, int]:
        """With some probability, overshoot past the target then correct back."""
        distance = math.hypot(x - sx, y - sy)
        if distance < self.overshoot_min_distance:
            return x, y
        if random.random() >= self.overshoot_probability:
            return x, y

        # Overshoot in the direction of travel
        angle = math.atan2(y - sy, x - sx)
        overshoot_dist = random.uniform(3, 12)
        ox = int(x + overshoot_dist * math.cos(angle))
        oy = int(y + overshoot_dist * math.sin(angle))

        # Move to overshoot point (already at target from main curve)
        move_fn(ox, oy)
        time.sleep(random.uniform(0.01, 0.03))

        # Correction: small number of steps back to actual target
        correction_steps = random.randint(3, 5)
        correction_duration = random.uniform(0.04, 0.12)
        t0 = time.perf_counter()
        for i in range(1, correction_steps + 1):
            frac = i / correction_steps
            # Linear interpolation with slight deceleration
            ease_frac = frac * frac * (3 - 2 * frac)
            cx = int(ox + (x - ox) * ease_frac)
            cy = int(oy + (y - oy) * ease_frac)
            move_fn(cx, cy)
            target = t0 + frac * correction_duration
            remaining = target - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

        return x, y

    # ── Protocol implementation ────────────────────────────────────────

    def move_to_target(self, x: int, y: int, move_fn: Callable[[int, int], None]) -> tuple[int, int]:
        sx, sy = _get_cursor_pos()
        self._bezier_move(sx, sy, x, y, move_fn)
        # Overshoot + correction (probabilistic)
        self._maybe_overshoot(x, y, sx, sy, move_fn)
        # Landing jitter
        jx = x + random.randint(-self.click_jitter, self.click_jitter)
        jy = y + random.randint(-self.click_jitter, self.click_jitter)
        move_fn(jx, jy)
        return jx, jy

    def pre_click_delay(self) -> None:
        time.sleep(lognormal_delay(0.035, sigma=0.3, lo=0.01, hi=0.15))

    def inter_click_delay(self) -> None:
        time.sleep(lognormal_delay(0.07, sigma=0.25, lo=0.03, hi=0.20))

    def pre_key_delay(self) -> None:
        lo, hi = self.key_delay_range
        median = (lo + hi) / 2
        time.sleep(lognormal_delay(median, sigma=0.4, lo=lo * 0.6, hi=hi * 2.0))

    def type_char_delay(self) -> None:
        lo, hi = self.type_delay_range
        median = (lo + hi) / 2
        time.sleep(lognormal_delay(median, sigma=0.35, lo=lo * 0.6, hi=hi * 2.7))

    def scroll_chunk(self, remaining: int) -> int:
        chunk_min = max(1, remaining // 5)
        chunk_max = max(2, remaining // 2)
        return min(remaining, random.randint(chunk_min, chunk_max))

    def inter_scroll_delay(self) -> None:
        time.sleep(lognormal_delay(0.04, sigma=0.3, lo=0.01, hi=0.15))

    def pre_drag_delay(self) -> None:
        time.sleep(lognormal_delay(0.06, sigma=0.3, lo=0.02, hi=0.25))
