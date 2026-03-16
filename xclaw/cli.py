import json
import time

import click


def _output(data: dict):
    """Print JSON to stdout for LLM consumption."""
    click.echo(json.dumps(data, ensure_ascii=False))


def _parse_region(region_str: str | None):
    """Parse 'x,y,w,h' string into tuple or return None."""
    if not region_str:
        return None
    parts = [int(p.strip()) for p in region_str.split(",")]
    if len(parts) != 4:
        raise click.BadParameter("region must be x,y,w,h")
    return tuple(parts)


@click.group()
def main():
    """X-Claw Visual Agent CLI"""
    pass


# ── P0: Basic actions ──────────────────────────────────────────────


@main.command()
@click.option("--region", default=None, help="x,y,w,h")
def screen(region):
    """Take a screenshot."""
    from xclaw.core.screen import take_screenshot

    result = take_screenshot(_parse_region(region))
    _output(result)


@main.command("click")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--double", is_flag=True, help="Double-click")
def click_cmd(x, y, double):
    """Click at screen coordinates."""
    from xclaw.action.mouse import click as do_click

    result = do_click(x, y, double=double)
    _output(result)


@main.command("type")
@click.argument("text")
def type_cmd(text):
    """Type text at the cursor."""
    from xclaw.action.keyboard import type_text

    result = type_text(text)
    _output(result)


@main.command()
@click.argument("key")
def press(key):
    """Press a key (enter, tab, escape, ...)."""
    from xclaw.action.keyboard import press_key

    result = press_key(key)
    _output(result)


@main.command()
@click.argument("direction", type=click.Choice(["up", "down"]))
@click.argument("amount", type=int)
def scroll(direction, amount):
    """Scroll up or down."""
    from xclaw.action.mouse import scroll as do_scroll

    result = do_scroll(direction, amount)
    _output(result)


@main.command()
@click.argument("seconds", type=float)
def wait(seconds):
    """Wait for a number of seconds."""
    time.sleep(seconds)
    _output({"status": "ok", "action": "wait", "seconds": seconds})


# ── P1: Visual parsing ─────────────────────────────────────────────


@main.command()
@click.argument("image_path")
def parse(image_path):
    """Parse a screenshot with OmniParser."""
    from xclaw.core.parser import ScreenParser

    parser = ScreenParser()
    result = parser.parse(image_path)
    _output(result)


# ── P2: Look = screen + pipeline ──────────────────────────────────


@main.command()
@click.option("--region", default=None, help="x,y,w,h")
@click.option("--depth", type=click.Choice(["l1", "l2", "l3"]), default="l3",
              help="Pipeline depth: l1=perception, l2=+spatial, l3=+semantic (default)")
def look(region, depth):
    """Screenshot + three-layer pipeline in one step."""
    from xclaw.core.screen import take_screenshot
    from xclaw.core.pipeline import run_pipeline
    from xclaw.core.cache import get_cache

    screen_result = take_screenshot(_parse_region(region))
    result = run_pipeline(
        screen_result["image_path"],
        skip_l2=(depth == "l1"),
        skip_l3=(depth in ("l1", "l2")),
    )
    get_cache().put(screen_result["image_path"], result)
    _output(result.to_dict())


# ── P2b: Status = pixel-diff change detection ────────────────────


@main.command()
def status():
    """Pixel-level diff to detect screen changes (no GPU)."""
    from xclaw.core.screen import take_screenshot
    from PIL import Image

    screen_result = take_screenshot()
    img = Image.open(screen_result["image_path"])

    # Downscale to 480x270 for fast comparison
    thumb = img.resize((480, 270), Image.LANCZOS)
    pixels = list(thumb.getdata())

    from xclaw.core.cache import get_cache
    cache = get_cache()
    prev = cache.get_latest()

    changed = True
    diff_ratio = 1.0
    t0 = time.time()

    if prev and prev.image_path:
        try:
            prev_img = Image.open(prev.image_path)
            prev_thumb = prev_img.resize((480, 270), Image.LANCZOS)
            prev_pixels = list(prev_thumb.getdata())

            total = len(pixels)
            diff_count = 0
            for cur, prv in zip(pixels, prev_pixels):
                if abs(cur[0] - prv[0]) + abs(cur[1] - prv[1]) + abs(cur[2] - prv[2]) > 30:
                    diff_count += 1

            diff_ratio = diff_count / total if total > 0 else 1.0
            changed = diff_ratio > 0.01
        except Exception:
            pass

    elapsed_ms = int((time.time() - t0) * 1000)
    _output({"changed": changed, "diff_ratio": round(diff_ratio, 4), "elapsed_ms": elapsed_ms})


# ── P3: Browser ───────────────────────────────────────────────────


@main.command()
def tabs():
    """List open Chrome tabs."""
    from xclaw.core.browser import list_tabs

    _output(list_tabs())


@main.command()
@click.argument("domain")
def tab(domain):
    """Switch to a Chrome tab by domain."""
    from xclaw.core.browser import switch_tab

    _output(switch_tab(domain))


if __name__ == "__main__":
    main()
