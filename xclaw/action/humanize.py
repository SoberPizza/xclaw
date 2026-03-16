"""Human-like mouse movement and typing patterns."""

import random
import time

import pyautogui

from xclaw.config import BEZIER_DURATION_RANGE, BEZIER_STEPS, TYPE_DELAY_RANGE


def bezier_point(t: float, p0, p1, p2, p3):
    """Compute a point on a cubic Bezier curve at parameter t."""
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def bezier_move(start: tuple, end: tuple, duration_range: tuple = None, steps: int = None):
    """Move the mouse along a cubic Bezier curve from start to end.

    Args:
        start: (x, y) starting position.
        end: (x, y) ending position.
        duration_range: (min, max) total duration in seconds.
        steps: Number of intermediate points on the curve.
    """
    if duration_range is None:
        duration_range = BEZIER_DURATION_RANGE
    if steps is None:
        steps = BEZIER_STEPS

    sx, sy = start
    ex, ey = end

    # Random control points for natural-looking curve
    dx = ex - sx
    dy = ey - sy
    cp1 = (sx + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
           sy + dy * random.uniform(0.0, 0.3) + random.uniform(-50, 50))
    cp2 = (sx + dx * random.uniform(0.6, 0.8) + random.uniform(-50, 50),
           sy + dy * random.uniform(0.7, 1.0) + random.uniform(-50, 50))

    duration = random.uniform(*duration_range)
    interval = duration / steps

    for i in range(1, steps + 1):
        t = i / steps
        # Ease-in-out: slow start and end
        t = t * t * (3 - 2 * t)
        px, py = bezier_point(t, (sx, sy), cp1, cp2, (ex, ey))
        pyautogui.moveTo(int(px), int(py), _pause=False)
        time.sleep(interval)


def humanized_click(x: int, y: int, double: bool = False):
    """Move to target with Bezier curve, then click.

    Args:
        x: Target X coordinate.
        y: Target Y coordinate.
        double: Double-click if True.
    """
    current = pyautogui.position()
    bezier_move((current.x, current.y), (x, y))

    # Small random offset for natural feel
    offset_x = random.randint(-2, 2)
    offset_y = random.randint(-2, 2)

    clicks = 2 if double else 1
    pyautogui.click(x + offset_x, y + offset_y, clicks=clicks)


def humanized_type(text: str, delay_range: tuple = None):
    """Type text with random inter-key delays.

    Args:
        text: Text to type.
        delay_range: (min, max) delay between keystrokes in seconds.
    """
    if delay_range is None:
        delay_range = TYPE_DELAY_RANGE

    try:
        text.encode("ascii")
        for char in text:
            pyautogui.press(char) if len(char) == 1 else pyautogui.press(char)
            time.sleep(random.uniform(*delay_range))
    except UnicodeEncodeError:
        import pyperclip
        pyperclip.copy(text)
        time.sleep(random.uniform(0.1, 0.3))
        pyautogui.hotkey("ctrl", "v")
