import json
import time

import click


def _output(data: dict):
    """Print JSON to stdout for LLM consumption."""
    click.echo(json.dumps(data, ensure_ascii=True))


def _cleanup_logs(keep: int = 50) -> None:
    """Remove old log files, keeping the most recent *keep* entries."""
    from xclaw.config import LOGS_DIR
    try:
        files = sorted(LOGS_DIR.glob("screen_*.json"))
        for f in files[:-keep]:
            f.unlink(missing_ok=True)
    except OSError:
        pass


def _save_to_logs(result_dict: dict, *, prefix: str = "screen", timestamp: int | None = None) -> str | None:
    """Persist result to LOGS_DIR. Returns file path or None on failure."""
    from xclaw.config import LOGS_DIR
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        if not timestamp:
            timestamp = int(time.time() * 1000)
        log_file = LOGS_DIR / f"{prefix}_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        latest_file = LOGS_DIR / f"{prefix}.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        _cleanup_logs()
        return str(log_file)
    except Exception as exc:
        click.echo(f"Warning: failed to save log: {exc}", err=True)
        return None


def _action_with_look(action_result: dict) -> tuple[dict, dict]:
    """Run the smart perception scheduler after an action and return (result, timing)."""
    from xclaw.core.context.scheduler import schedule

    sr = schedule(action_result=action_result)
    perception = sr.perception
    meta = perception.pop("_perception", {})
    result = {
        "action": action_result,
        "perception": perception,
        "_meta": {
            "level": sr.level,
            "diff_ratio": sr.diff_ratio,
            "changed": meta.get("changed"),
            "elapsed_ms": sr.elapsed_ms,
        },
    }
    _save_to_logs(result, timestamp=sr.timestamp)
    return result, sr.timing


def _ensure_cuda_dll_dirs():
    """Register nvidia DLL directories and pre-load torch for CUDA support.

    On Windows, ``nvidia-*-cu12`` packages install DLLs under
    ``site-packages/nvidia/<lib>/bin/``.  These directories must be
    registered via ``os.add_dll_directory`` before torch can load its
    CUDA libraries.  Importing torch early then ensures CUDA DLLs are
    findable by later imports (e.g. onnxruntime-gpu, torchvision).
    """
    import os
    import sys

    if sys.platform != "win32":
        return

    # Register nvidia/*/bin/ directories so CUDA DLLs are findable
    import site

    for sp in site.getsitepackages():
        nvidia_dir = os.path.join(sp, "nvidia")
        if not os.path.isdir(nvidia_dir):
            continue
        for sub in os.listdir(nvidia_dir):
            bin_dir = os.path.join(nvidia_dir, sub, "bin")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)

    # Import torch early — registers torch/lib/ and bundled CUDA DLLs
    try:
        import torch  # noqa: F401
    except Exception:
        pass


def _silence_for_cli():
    """Suppress all non-JSON output when running as CLI (for LLM consumption)."""
    import logging
    import os
    import warnings

    # Python logging → CRITICAL only
    logging.getLogger().setLevel(logging.CRITICAL)

    # Python warnings → off
    warnings.filterwarnings("ignore")

    # Third-party env vars
    os.environ["NO_COLOR"] = "1"
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["YOLO_VERBOSE"] = "False"

    # ONNX Runtime (C++ layer) — 3=Error
    os.environ["ORT_LOG_LEVEL"] = "3"

    # transformers / huggingface_hub tqdm progress bars
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"


def _print_timing(timing: dict, cli_start_ns: int) -> None:
    """Print timing breakdown to stderr (does not pollute stdout JSON)."""
    total_ms = (time.perf_counter_ns() - cli_start_ns) // 1_000_000
    click.echo(f"\n--- Timing (total {total_ms}ms) ---", err=True)
    _print_timing_dict(timing, indent=0)
    click.echo(f"cli_total_ms: {total_ms}", err=True)


def _print_timing_dict(d: dict, indent: int = 0) -> None:
    """Recursively print timing dict with indentation."""
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, dict):
            click.echo(f"{prefix}{key}:", err=True)
            _print_timing_dict(value, indent + 1)
        else:
            click.echo(f"{prefix}{key}: {value}", err=True)


@click.group()
@click.option("--timing", "show_timing", is_flag=True, help="Print timing breakdown to stderr")
@click.pass_context
def main(ctx, show_timing):
    """X-Claw Visual Agent CLI"""
    ctx.ensure_object(dict)
    ctx.obj["show_timing"] = show_timing
    ctx.obj["cli_start_ns"] = time.perf_counter_ns()
    _silence_for_cli()
    _ensure_cuda_dll_dirs()


# ── Perception ────────────────────────────────────────────────────


@main.command()
@click.pass_context
def look(ctx):
    """Observe the screen."""
    from xclaw.core.context.scheduler import schedule

    sr = schedule()
    perception = sr.perception
    meta = perception.pop("_perception", {})
    result = {
        **perception,
        "_meta": {
            "level": sr.level,
            "diff_ratio": sr.diff_ratio,
            "changed": meta.get("changed"),
            "elapsed_ms": sr.elapsed_ms,
        },
    }
    _save_to_logs(result, timestamp=sr.timestamp)
    _output(result)
    if ctx.obj.get("show_timing"):
        _print_timing(sr.timing, ctx.obj["cli_start_ns"])


# ── Actions ───────────────────────────────────────────────────────


@main.command("click")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--double", is_flag=True, help="Double-click")
@click.pass_context
def click_cmd(ctx, x, y, double):
    """Click at screen coordinates."""
    from xclaw.action.mouse import click as do_click

    result, sched_timing = _action_with_look(do_click(x, y, double=double))
    _output(result)
    if ctx.obj.get("show_timing"):
        _print_timing(sched_timing, ctx.obj["cli_start_ns"])


@main.command("type")
@click.argument("text")
@click.pass_context
def type_cmd(ctx, text):
    """Type text at the cursor."""
    from xclaw.action.keyboard import type_text

    result, sched_timing = _action_with_look(type_text(text))
    _output(result)
    if ctx.obj.get("show_timing"):
        _print_timing(sched_timing, ctx.obj["cli_start_ns"])


@main.command()
@click.argument("key")
@click.pass_context
def press(ctx, key):
    """Press a key (enter, tab, escape, ...)."""
    from xclaw.action.keyboard import press_key

    result, sched_timing = _action_with_look(press_key(key))
    _output(result)
    if ctx.obj.get("show_timing"):
        _print_timing(sched_timing, ctx.obj["cli_start_ns"])


@main.command()
@click.argument("direction", type=click.Choice(["up", "down"]))
@click.argument("amount", type=int)
@click.option("--x", type=int, default=None, help="X coordinate (default: screen center)")
@click.option("--y", type=int, default=None, help="Y coordinate (default: screen center)")
@click.pass_context
def scroll(ctx, direction, amount, x, y):
    """Scroll up or down."""
    from xclaw.action.mouse import scroll as do_scroll

    result, sched_timing = _action_with_look(do_scroll(direction, amount, x, y))
    _output(result)
    if ctx.obj.get("show_timing"):
        _print_timing(sched_timing, ctx.obj["cli_start_ns"])


@main.command()
@click.argument("seconds", type=float)
@click.pass_context
def wait(ctx, seconds):
    """Wait for a number of seconds."""
    time.sleep(seconds)
    action_result = {"status": "ok", "action": "wait", "seconds": seconds}
    result, sched_timing = _action_with_look(action_result)
    _output(result)
    if ctx.obj.get("show_timing"):
        _print_timing(sched_timing, ctx.obj["cli_start_ns"])


# ── Server ───────────────────────────────────────────────────────


@main.command()
@click.pass_context
def serve(ctx):
    """Start long-running stdio server."""
    from xclaw.serve import run_serve
    run_serve()


if __name__ == "__main__":
    main()
