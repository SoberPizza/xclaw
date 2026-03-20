"""stdio JSON-line server — keeps models loaded across requests.

Launch:  xclaw serve
Proto:   one JSON object per line on stdin, one JSON response per line on stdout.
Exit:    close stdin or kill the process.
"""

from __future__ import annotations

import json
import sys
import time

from xclaw import __version__


def _write(data: dict) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _dispatch(request: dict) -> dict:
    """Route a single request to the appropriate handler."""
    cmd = request.get("command")

    if cmd == "look":
        return _handle_look()

    if cmd in ("click", "type", "press", "scroll", "wait"):
        return _handle_action(cmd, request)

    return {"status": "error", "message": f"unknown command: {cmd}"}


def _handle_look() -> dict:
    from xclaw.core.context.scheduler import schedule

    sr = schedule()
    perception = sr.perception
    meta = perception.pop("_perception", {})
    return {
        "status": "ok",
        **perception,
        "_meta": {
            "level": sr.level,
            "diff_ratio": sr.diff_ratio,
            "changed": meta.get("changed"),
            "elapsed_ms": sr.elapsed_ms,
        },
    }


def _handle_action(cmd: str, request: dict) -> dict:
    # Execute the action
    if cmd == "click":
        from xclaw.action.mouse import click as do_click
        action_result = do_click(
            request["x"], request["y"],
            double=request.get("double", False),
        )
    elif cmd == "type":
        from xclaw.action.keyboard import type_text
        action_result = type_text(request["text"])
    elif cmd == "press":
        from xclaw.action.keyboard import press_key
        action_result = press_key(request["key"])
    elif cmd == "scroll":
        from xclaw.action.mouse import scroll as do_scroll
        action_result = do_scroll(
            request["direction"], request["amount"],
            request.get("x"), request.get("y"),
        )
    elif cmd == "wait":
        time.sleep(request.get("seconds", 1))
        action_result = {
            "status": "ok", "action": "wait",
            "seconds": request.get("seconds", 1),
        }
    else:
        return {"status": "error", "message": f"unknown action: {cmd}"}

    # Run perception after the action
    from xclaw.core.context.scheduler import schedule

    sr = schedule(action_result=action_result)
    perception = sr.perception
    meta = perception.pop("_perception", {})
    return {
        "status": "ok",
        "action": action_result,
        "perception": perception,
        "_meta": {
            "level": sr.level,
            "diff_ratio": sr.diff_ratio,
            "changed": meta.get("changed"),
            "elapsed_ms": sr.elapsed_ms,
        },
    }


def run_serve() -> None:
    """stdio JSON-line server main loop."""
    from xclaw.cli import _silence_for_cli, _ensure_cuda_dll_dirs

    _silence_for_cli()
    _ensure_cuda_dll_dirs()

    # Pre-load perception engine
    try:
        from xclaw.core.perception.engine import PerceptionEngine

        engine = PerceptionEngine.get_instance()
        engine._ensure_models()
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        _write({"status": "error", "message": f"model load failed: {exc}"})
        sys.exit(1)

    # Signal ready
    _write({"status": "ready", "version": __version__})

    # Main loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            _write({"status": "error", "message": "invalid JSON"})
            continue

        try:
            response = _dispatch(request)
        except Exception as exc:
            import traceback
            traceback.print_exc(file=sys.stderr)
            response = {"status": "error", "message": str(exc)}

        _write(response)
