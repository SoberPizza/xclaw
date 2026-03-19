import json
import time

import click


def _output(data: dict):
    """Print JSON to stdout for LLM consumption."""
    click.echo(json.dumps(data, ensure_ascii=True))


def _extract_ts(image_path: str) -> int | None:
    """Extract millisecond timestamp from 'screen_1234567890123.png'."""
    import re
    m = re.search(r"screen_(\d+)\.", image_path)
    return int(m.group(1)) if m else None


def _save_to_logs(result_dict: dict, *, prefix: str = "screen", timestamp: int | None = None) -> str | None:
    """Persist result to LOGS_DIR. Returns file path or None on failure."""
    from xclaw.config import LOGS_DIR
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        log_file = LOGS_DIR / f"{prefix}_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        latest_file = LOGS_DIR / f"{prefix}.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        return str(log_file)
    except Exception as exc:
        click.echo(f"Warning: failed to save log: {exc}", err=True)
        return None


def _action_with_look(action_result: dict) -> dict:
    """Run the smart perception scheduler (via daemon) after an action and return combined result."""
    from xclaw.core.daemon import request_perception

    resp = request_perception({
        "command": "schedule",
        "action_result": action_result,
    })
    perception = resp.get("perception", resp)
    meta = perception.pop("_perception", {})
    return {
        "action": action_result,
        "perception": perception,
        "_meta": {
            "level": resp.get("level", meta.get("level")),
            "diff_ratio": resp.get("diff_ratio", meta.get("diff_ratio")),
            "changed": meta.get("changed"),
            "elapsed_ms": resp.get("elapsed_ms", meta.get("elapsed_ms")),
        },
    }


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

    # Disable ANSI color codes from colorlog (used by PaddleX)
    os.environ["NO_COLOR"] = "1"

    # Third-party env vars
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["YOLO_VERBOSE"] = "False"

    # PaddlePaddle GLOG (C++ layer) — 2=ERROR, suppresses INFO+WARNING
    os.environ["GLOG_minloglevel"] = "2"

    # PaddleX: skip connectivity check + disable oneDNN (PIR+oneDNN bug on Win CPU)
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "1"
    os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"

    # Pre-configure paddlex logger BEFORE paddlex is imported.
    # PaddleX's setup_logging() checks hasHandlers() — pre-adding NullHandler
    # prevents it from registering its colorlog StreamHandler.
    for name in ("paddlex", "paddlex.inference", "paddlex.utils"):
        lg = logging.getLogger(name)
        lg.addHandler(logging.NullHandler())
        lg.setLevel(logging.CRITICAL)
        lg.propagate = False

    # ONNX Runtime (C++ layer) — 3=Error
    os.environ["ORT_LOG_LEVEL"] = "3"

    # transformers / huggingface_hub tqdm progress bars
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"


@click.group()
def main():
    """X-Claw Visual Agent CLI"""
    _silence_for_cli()
    _ensure_cuda_dll_dirs()


# ── Perception ────────────────────────────────────────────────────


@main.command()
def look():
    """Observe the screen."""
    from xclaw.core.daemon import request_perception

    resp = request_perception({"command": "schedule"})
    perception = resp.get("perception", resp)
    meta = perception.pop("_perception", {})
    result = {
        **perception,
        "_meta": {
            "level": resp.get("level", meta.get("level")),
            "diff_ratio": resp.get("diff_ratio", meta.get("diff_ratio")),
            "changed": meta.get("changed"),
            "elapsed_ms": resp.get("elapsed_ms", meta.get("elapsed_ms")),
        },
    }
    _save_to_logs(result)
    _output(result)


# ── Actions ───────────────────────────────────────────────────────


@main.command("click")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--double", is_flag=True, help="Double-click")
def click_cmd(x, y, double):
    """Click at screen coordinates."""
    from xclaw.action.mouse import click as do_click

    result = do_click(x, y, double=double)
    _output(_action_with_look(result))


@main.command("type")
@click.argument("text")
def type_cmd(text):
    """Type text at the cursor."""
    from xclaw.action.keyboard import type_text

    result = type_text(text)
    _output(_action_with_look(result))


@main.command()
@click.argument("key")
def press(key):
    """Press a key (enter, tab, escape, ...)."""
    from xclaw.action.keyboard import press_key

    result = press_key(key)
    _output(_action_with_look(result))


@main.command()
@click.argument("direction", type=click.Choice(["up", "down"]))
@click.argument("amount", type=int)
@click.option("--x", type=int, default=None, help="X coordinate (default: screen center)")
@click.option("--y", type=int, default=None, help="Y coordinate (default: screen center)")
def scroll(direction, amount, x, y):
    """Scroll up or down."""
    from xclaw.action.mouse import scroll as do_scroll

    result = do_scroll(direction, amount, x, y)
    _output(_action_with_look(result))


@main.command()
@click.argument("seconds", type=float)
def wait(seconds):
    """Wait for a number of seconds."""
    time.sleep(seconds)
    result = {"status": "ok", "action": "wait", "seconds": seconds}
    _output(_action_with_look(result))


# ── Emergency ─────────────────────────────────────────────────────


@main.command()
def stop():
    """Emergency stop: kill the perception daemon.

    Use ONLY when the daemon is stuck or crashed. Under normal operation
    the daemon exits automatically after 300 seconds of idle time.
    """
    from xclaw.core.daemon import is_daemon_alive, request_perception
    if is_daemon_alive():
        try:
            request_perception({"command": "shutdown"})
        except Exception:
            pass
        _output({"status": "stopped"})
    else:
        _output({"status": "not_running"})


if __name__ == "__main__":
    main()
