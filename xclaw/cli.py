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


def _perceive_after_action(action_result: dict) -> dict:
    """Run the smart perception scheduler after an action."""
    from xclaw.core.context.scheduler import schedule

    sr = schedule(action_result)
    meta = sr.perception.pop("_perception", {})
    return {
        "level": sr.level,
        "confidence": round(sr.confidence, 2),
        "escalation_path": sr.escalation_path,
        "elapsed_ms": sr.elapsed_ms,
        **meta,
    }


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
@click.option("--no-perceive", is_flag=True, help="Skip auto perception")
def click_cmd(x, y, double, no_perceive):
    """Click at screen coordinates."""
    from xclaw.action.mouse import click as do_click

    result = do_click(x, y, double=double)
    if not no_perceive:
        result["_perception"] = _perceive_after_action(result)
    _output(result)


@main.command("type")
@click.argument("text")
@click.option("--no-perceive", is_flag=True, help="Skip auto perception")
def type_cmd(text, no_perceive):
    """Type text at the cursor."""
    from xclaw.action.keyboard import type_text

    result = type_text(text)
    if not no_perceive:
        result["_perception"] = _perceive_after_action(result)
    _output(result)


@main.command()
@click.argument("key")
@click.option("--no-perceive", is_flag=True, help="Skip auto perception")
def press(key, no_perceive):
    """Press a key (enter, tab, escape, ...)."""
    from xclaw.action.keyboard import press_key

    result = press_key(key)
    if not no_perceive:
        result["_perception"] = _perceive_after_action(result)
    _output(result)


@main.command()
@click.argument("direction", type=click.Choice(["up", "down"]))
@click.argument("amount", type=int)
@click.option("--x", type=int, default=None, help="X coordinate (default: screen center)")
@click.option("--y", type=int, default=None, help="Y coordinate (default: screen center)")
@click.option("--no-perceive", is_flag=True, help="Skip auto perception")
def scroll(direction, amount, x, y, no_perceive):
    """Scroll up or down."""
    from xclaw.action.mouse import scroll as do_scroll

    result = do_scroll(direction, amount, x, y)
    if not no_perceive:
        result["_perception"] = _perceive_after_action(result)
    _output(result)


@main.command()
@click.argument("seconds", type=float)
@click.option("--no-perceive", is_flag=True, help="Skip auto perception")
def wait(seconds, no_perceive):
    """Wait for a number of seconds."""
    time.sleep(seconds)
    result = {"status": "ok", "action": "wait", "seconds": seconds}
    if not no_perceive:
        result["_perception"] = _perceive_after_action(result)
    _output(result)


# ── P1: Visual parsing ─────────────────────────────────────────────


@main.command()
@click.argument("image_path")
@click.option("--clean", is_flag=True, help="Suppress logs/warnings for clean JSON output")
def parse(image_path, clean):
    """Parse a screenshot with OmniParser."""
    import logging
    import sys
    import io
    from pathlib import Path
    from xclaw.config import LOGS_DIR

    if clean:
        # Redirect stderr to suppress C/C++ warnings
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        # Suppress Python logs
        logging.getLogger().setLevel(logging.CRITICAL)
        import warnings
        warnings.filterwarnings("ignore")

    try:
        # Use singleton parser with log suppression on first call
        from xclaw.core.perception.omniparser import get_parser
        parser = get_parser(suppress_logs=clean)
        result = parser.parse(image_path)

        # Persist result to logs folder
        LOGS_DIR.mkdir(exist_ok=True)
        timestamp = int(time.time() * 1000)
        log_file = LOGS_DIR / f"screen_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        latest_file = LOGS_DIR / "screen.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        _output(result)
    finally:
        if clean:
            sys.stderr = old_stderr


# ── P2: Look = screen + pipeline ──────────────────────────────────


@main.command()
def init():
    """Initialize X-Claw: verify models and dependencies."""
    import sys
    import io
    from xclaw.core.perception.omniparser import get_parser

    try:
        click.echo("Initializing X-Claw...", err=True)
        click.echo("Loading OmniParser models (this may take a while on first run)...", err=True)

        # Initialize parser (with full logging output)
        parser = get_parser(suppress_logs=False)

        click.echo("✓ OmniParser initialized successfully", err=True)
        click.echo("✓ All models loaded", err=True)

        _output({
            "status": "ok",
            "message": "X-Claw initialization complete",
            "components": {
                "omniparser": "ready",
                "paddleocr": "ready",
                "device": "cuda" if __import__('torch').cuda.is_available() else "cpu",
            }
        })
    except Exception as e:
        click.echo(f"✗ Initialization failed: {e}", err=True)
        _output({
            "status": "error",
            "error": str(e),
        })
        sys.exit(1)


@main.command()
@click.option("--region", default=None, help="x,y,w,h")
@click.option("--depth", type=click.Choice(["l1", "l2", "l3"]), default="l3",
              help="Pipeline depth: l1=perception, l2=+spatial, l3=+semantic (default)")
@click.option("--clean", is_flag=True, help="Suppress logs/warnings for clean JSON output")
def look(region, depth, clean):
    """Screenshot + three-layer pipeline in one step."""
    import logging
    import sys
    import io
    from pathlib import Path
    from xclaw.core.screen import take_screenshot
    from xclaw.core.pipeline import run_pipeline
    from xclaw.core.cache import get_cache
    from xclaw.core.context.state import ContextState
    from xclaw.core.context.glance import _elements_to_dicts
    from xclaw.config import LOGS_DIR

    # Suppress all logs if --clean flag is set
    if clean:
        # Capture stderr to suppress C/C++ warnings
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        # Set Python logging to CRITICAL
        root_logger = logging.getLogger()
        old_level = root_logger.level
        root_logger.setLevel(logging.CRITICAL)

        # Suppress all warnings
        import warnings
        warnings.filterwarnings("ignore")

    try:
        screen_result = take_screenshot(_parse_region(region))
        result = run_pipeline(
            screen_result["image_path"],
            skip_l2=(depth == "l1"),
            skip_l3=(depth in ("l1", "l2")),
        )
        get_cache().put(screen_result["image_path"], result)

        # Update ContextState after look
        level_map = {"l1": "L1", "l2": "L2", "l3": "L3"}
        level = level_map[depth]
        state = ContextState.load() or ContextState()
        state.record_perception(
            level,
            result_dict=result.to_dict(),
            screenshot_path=screen_result["image_path"],
            elements=_elements_to_dicts(result.elements),
            resolution=result.resolution,
        )
        if level == "L3":
            state.confidence = 1.0
        state.save()

        # Persist parsing result to logs folder
        result_dict = result.to_dict()
        LOGS_DIR.mkdir(exist_ok=True)

        # Save with timestamp filename
        timestamp = int(time.time() * 1000)
        log_file = LOGS_DIR / f"screen_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        # Also update screen.json as latest result
        latest_file = LOGS_DIR / "screen.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        _output(result_dict)
    finally:
        if clean:
            sys.stderr = old_stderr
            root_logger.setLevel(old_level)


# ── P2b: Status = pixel-diff change detection ────────────────────


@main.command()
def status():
    """Pixel-level diff to detect screen changes (no GPU)."""
    from xclaw.core.screen import take_screenshot
    from xclaw.core.context.state import ContextState
    from xclaw.core.context.peek import peek

    screen_result = take_screenshot()
    state = ContextState.load() or ContextState()
    result = peek(state, screen_result["image_path"])

    _output({
        "changed": result.changed,
        "diff_ratio": result.diff_ratio,
        "change_regions": result.change_regions,
        "elapsed_ms": result.elapsed_ms,
    })


# ── P2c: Peek / Glance = manual perception levels ────────────────


@main.command("peek")
def peek_cmd():
    """L1 pixel diff — detect screen changes without GPU."""
    from xclaw.core.screen import take_screenshot
    from xclaw.core.context.state import ContextState
    from xclaw.core.context.peek import peek
    from xclaw.config import LOGS_DIR

    screen_result = take_screenshot()
    state = ContextState.load() or ContextState()
    result = peek(state, screen_result["image_path"])

    state.record_perception("L1", screenshot_path=screen_result["image_path"])
    state.save()

    result_dict = {
        "level": "L1",
        "changed": result.changed,
        "diff_ratio": result.diff_ratio,
        "change_regions": result.change_regions,
        "elapsed_ms": result.elapsed_ms,
    }

    # Persist result to logs folder
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = int(time.time() * 1000)
    log_file = LOGS_DIR / f"screen_{timestamp}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    latest_file = LOGS_DIR / "screen.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    _output(result_dict)


@main.command("glance")
def glance_cmd():
    """L2 incremental parse — re-parse only changed regions."""
    from xclaw.core.screen import take_screenshot
    from xclaw.core.context.state import ContextState
    from xclaw.core.context.peek import peek
    from xclaw.core.context.glance import glance, _elements_to_dicts
    from xclaw.config import LOGS_DIR

    screen_result = take_screenshot()
    state = ContextState.load() or ContextState()
    peek_result = peek(state, screen_result["image_path"])

    if not peek_result.changed or not peek_result.change_regions:
        result_dict = {
            "level": "L1",
            "changed": False,
            "diff_ratio": peek_result.diff_ratio,
            "elapsed_ms": peek_result.elapsed_ms,
        }

        # Persist result to logs folder
        LOGS_DIR.mkdir(exist_ok=True)
        timestamp = int(time.time() * 1000)
        log_file = LOGS_DIR / f"screen_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        latest_file = LOGS_DIR / "screen.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        _output(result_dict)
        return

    try:
        glance_result = glance(
            screen_result["image_path"],
            peek_result.change_regions,
            state,
        )
    except Exception as exc:
        result_dict = {"level": "L2", "error": f"glance failed: {exc}", "changed": True,
                       "diff_ratio": peek_result.diff_ratio}

        # Persist error result to logs folder
        LOGS_DIR.mkdir(exist_ok=True)
        timestamp = int(time.time() * 1000)
        log_file = LOGS_DIR / f"screen_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        latest_file = LOGS_DIR / "screen.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)

        _output(result_dict)
        return

    state.record_perception(
        "L2",
        result_dict=glance_result.pipeline_result.to_dict(),
        screenshot_path=screen_result["image_path"],
        elements=_elements_to_dicts(glance_result.pipeline_result.elements),
        resolution=glance_result.pipeline_result.resolution,
    )
    state.save()

    result_dict = glance_result.pipeline_result.to_dict()
    result_dict["level"] = "L2"
    result_dict["merged_from_cache"] = glance_result.merged_from_cache
    result_dict["newly_parsed"] = glance_result.newly_parsed
    result_dict["elapsed_ms"] = glance_result.elapsed_ms

    # Persist result to logs folder
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = int(time.time() * 1000)
    log_file = LOGS_DIR / f"screen_{timestamp}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    latest_file = LOGS_DIR / "screen.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    _output(result_dict)


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
