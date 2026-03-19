"""Windows mouse control via ctypes SendInput."""

import ctypes
import ctypes.wintypes
import time
import random

user32 = ctypes.windll.user32

# SendInput constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT_UNION),
    ]


def _screen_size() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _cursor_pos() -> tuple[int, int]:
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _to_absolute(x: int, y: int) -> tuple[int, int]:
    """Convert pixel coordinates to absolute coordinates (0-65535)."""
    w, h = _screen_size()
    ax = int(x * 65535 / w)
    ay = int(y * 65535 / h)
    return ax, ay


def _send_mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = dx
    inp.mi.dy = dy
    inp.mi.mouseData = data
    inp.mi.dwFlags = flags
    inp.mi.time = 0
    inp.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def move_to(x: int, y: int):
    ax, ay = _to_absolute(x, y)
    _send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)


def click(x: int, y: int, button: str = "left"):
    move_to(x, y)

    btn_map = {
        "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }
    down_flag, up_flag = btn_map.get(button, btn_map["left"])

    ax, ay = _to_absolute(x, y)
    _send_mouse(down_flag | MOUSEEVENTF_ABSOLUTE, ax, ay)
    time.sleep(random.uniform(0.04, 0.09))
    _send_mouse(up_flag | MOUSEEVENTF_ABSOLUTE, ax, ay)


def double_click(x: int, y: int):
    move_to(x, y)

    ax, ay = _to_absolute(x, y)
    for _ in range(2):
        _send_mouse(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, ax, ay)
        time.sleep(random.uniform(0.02, 0.05))
        _send_mouse(MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, ax, ay)
        time.sleep(random.uniform(0.05, 0.10))


def scroll(direction: str = "down", steps: int = 3):
    delta = WHEEL_DELTA if direction == "up" else -WHEEL_DELTA
    for _ in range(steps):
        _send_mouse(MOUSEEVENTF_WHEEL, data=delta)
        time.sleep(random.uniform(0.05, 0.15))
