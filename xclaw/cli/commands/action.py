"""Action commands — click, type, press, scroll, wait."""

import json
import time
import logging

import click

from xclaw.cli.core import output

logger = logging.getLogger(__name__)


def _action_with_look(action_result: dict) -> str:
    """Execute action then run full perception, return combined JSON."""
    from xclaw.core.perception.engine import PerceptionEngine

    engine = PerceptionEngine.get_instance()
    perception = engine.full_look()
    combined = {
        "action": action_result,
        "perception": perception,
    }
    return json.dumps(combined, ensure_ascii=False)


@click.command("click")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--double", is_flag=True, help="Double-click")
@click.option("--button", type=click.Choice(["left", "right", "middle"]), default="left", help="Mouse button")
def click_cmd(x, y, double, button):
    """Click at screen coordinates."""
    from xclaw.action.mouse import click as do_click

    result = do_click(x, y, double=double, button=button)
    output(_action_with_look(result))


@click.command("type")
@click.argument("text")
def type_cmd(text):
    """Type text at the cursor."""
    from xclaw.action.keyboard import type_text

    result = type_text(text)
    output(_action_with_look(result))


@click.command()
@click.argument("key")
def press(key):
    """Press a key (enter, tab, escape, ...)."""
    from xclaw.action.keyboard import press_key

    result = press_key(key)
    output(_action_with_look(result))


@click.command()
@click.argument("direction", type=click.Choice(["up", "down", "left", "right"]))
@click.argument("amount", type=int)
@click.option("--x", type=int, default=None, help="X coordinate (default: screen center)")
@click.option("--y", type=int, default=None, help="Y coordinate (default: screen center)")
def scroll(direction, amount, x, y):
    """Scroll up, down, left, or right."""
    from xclaw.action.mouse import scroll as do_scroll

    result = do_scroll(direction, amount, x, y)
    output(_action_with_look(result))


@click.command()
@click.argument("seconds", type=float)
def wait(seconds):
    """Wait for a number of seconds."""
    time.sleep(seconds)
    result = {"status": "ok", "action": "wait", "seconds": seconds}
    output(_action_with_look(result))


@click.command()
@click.argument("combo")
def hotkey(combo):
    """Execute a key combination (e.g. ctrl+c, alt+f4, ctrl+shift+t)."""
    from xclaw.action.keyboard import hotkey as do_hotkey

    result = do_hotkey(combo)
    output(_action_with_look(result))


@click.command()
@click.argument("x1", type=int)
@click.argument("y1", type=int)
@click.argument("x2", type=int)
@click.argument("y2", type=int)
@click.option("--button", type=click.Choice(["left", "right", "middle"]), default="left", help="Mouse button")
def drag(x1, y1, x2, y2, button):
    """Drag from (X1, Y1) to (X2, Y2)."""
    from xclaw.action.mouse import drag as do_drag

    result = do_drag(x1, y1, x2, y2, button=button)
    output(_action_with_look(result))


@click.command()
@click.argument("x", type=int)
@click.argument("y", type=int)
def move(x, y):
    """Move cursor to (X, Y) without clicking."""
    from xclaw.action import get_backend

    backend = get_backend()
    backend.move_to(x, y)
    result = {"status": "ok", "action": "move", "x": x, "y": y}
    output(_action_with_look(result))


@click.command()
def cursor():
    """Query cursor position and screen size."""
    from xclaw.action import get_backend

    backend = get_backend()
    cx, cy = backend.cursor_pos()
    sw, sh = backend.screen_size()
    result = {"cursor": [cx, cy], "screen": [sw, sh]}
    output(json.dumps(result, ensure_ascii=False))


@click.command()
@click.argument("button", type=click.Choice(["left", "right", "middle"]))
@click.argument("state", type=click.Choice(["down", "up"]))
@click.option("--x", type=int, default=None, help="X coordinate (default: current cursor)")
@click.option("--y", type=int, default=None, help="Y coordinate (default: current cursor)")
def hold(button, state, x, y):
    """Hold or release a mouse button (e.g. hold left down --x 100 --y 200)."""
    from xclaw.action import get_backend

    backend = get_backend()
    if x is None or y is None:
        cx, cy = backend.cursor_pos()
        x = x if x is not None else cx
        y = y if y is not None else cy

    if state == "down":
        result = backend.mouse_down(x, y, button)
    else:
        result = backend.mouse_up(x, y, button)
    output(_action_with_look(result))
