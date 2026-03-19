"""macOS mouse control via Quartz CGEvent."""

import time
import random

import Quartz


def _screen_size() -> tuple[int, int]:
    main = Quartz.CGMainDisplayID()
    return Quartz.CGDisplayPixelsWide(main), Quartz.CGDisplayPixelsHigh(main)


def _cursor_pos() -> tuple[int, int]:
    loc = Quartz.NSEvent.mouseLocation()
    _, h = _screen_size()
    return int(loc.x), int(h - loc.y)  # NSEvent y is from bottom, flip


def move_to(x: int, y: int):
    event = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def click(x: int, y: int, button: str = "left"):
    move_to(x, y)

    btn_map = {
        "left": (
            Quartz.kCGEventLeftMouseDown,
            Quartz.kCGEventLeftMouseUp,
            Quartz.kCGMouseButtonLeft,
        ),
        "right": (
            Quartz.kCGEventRightMouseDown,
            Quartz.kCGEventRightMouseUp,
            Quartz.kCGMouseButtonRight,
        ),
        "middle": (
            Quartz.kCGEventOtherMouseDown,
            Quartz.kCGEventOtherMouseUp,
            Quartz.kCGMouseButtonCenter,
        ),
    }
    down_t, up_t, btn = btn_map.get(button, btn_map["left"])

    ev_down = Quartz.CGEventCreateMouseEvent(None, down_t, (x, y), btn)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_down)
    time.sleep(random.uniform(0.04, 0.09))

    ev_up = Quartz.CGEventCreateMouseEvent(None, up_t, (x, y), btn)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)


def double_click(x: int, y: int):
    move_to(x, y)

    for n in (1, 2):
        for down in (True, False):
            evt_type = (
                Quartz.kCGEventLeftMouseDown if down
                else Quartz.kCGEventLeftMouseUp
            )
            ev = Quartz.CGEventCreateMouseEvent(
                None, evt_type, (x, y), Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventSetIntegerValueField(
                ev, Quartz.kCGMouseEventClickState, n
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(random.uniform(0.02, 0.05))
        if n == 1:
            time.sleep(random.uniform(0.05, 0.10))


def scroll(direction: str = "down", steps: int = 3):
    delta = -3 if direction == "down" else 3
    for _ in range(steps):
        ev = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 1, delta
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(random.uniform(0.05, 0.15))
