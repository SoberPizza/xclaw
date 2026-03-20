"""Scheduler — orchestrates L1→L3 perception with pure diff-based decisions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from xclaw.config import (
    CONTEXT_MAX_CONSECUTIVE_CHEAP,
    CONTEXT_POST_ACTION_DELAY,
)
from xclaw.core.context.state import ContextState
from xclaw.core.context.peek import peek
from xclaw.core.context.glance import glance, _elements_to_dicts
from xclaw.core.screen import take_screenshot
from xclaw.core.pipeline import run_pipeline

logger = logging.getLogger(__name__)


@dataclass
class SchedulerResult:
    """Output of the scheduler."""

    level: str  # "L1" | "L2" | "L3"
    perception: dict  # perception output
    diff_ratio: float
    escalation_path: list[str]  # e.g. ["L1", "L2"]
    elapsed_ms: int
    timestamp: int = 0  # screenshot epoch ms, for correlating logs
    timing: dict[str, object] = field(default_factory=dict)


def _run_full(
    screenshot_path: str,
    state: ContextState,
    escalation: list[str] | None = None,
    timing: dict[str, object] | None = None,
    timestamp: int = 0,
) -> SchedulerResult:
    """Full L3 pipeline."""
    if timing is None:
        timing = {}
    t0 = time.perf_counter_ns()
    result = run_pipeline(screenshot_path)
    timing["pipeline_ms"] = (time.perf_counter_ns() - t0) // 1_000_000
    timing["pipeline"] = result.timing
    result_dict = result.to_dict()

    state.record_perception(
        "L3",
        result_dict=result_dict,
        screenshot_path=screenshot_path,
        elements=_elements_to_dicts(result.elements),
        resolution=result.resolution,
    )
    state.save()

    elapsed = (time.perf_counter_ns() - t0) // 1_000_000
    path = (escalation or []) + ["L3"]
    return SchedulerResult(
        level="L3", perception=result_dict, diff_ratio=1.0,
        escalation_path=path, elapsed_ms=elapsed,
        timestamp=timestamp, timing=timing,
    )


def schedule(
    action_result: dict | None = None,
    *,
    force_level: str | None = None,
) -> SchedulerResult:
    """Run the smart perception scheduler — the recommended entry point.

    Every call takes a screenshot and runs pixel diff as the sole decision
    maker.  No confidence decay or action-type prediction.

    Decision flow:
    1. Force L3 if: no state, force_level="L3", too many cheap, stale cache
    2. L1 Peek: pixel diff (always runs)
       - diff < 1% → return cache (L1)
       - diff < 15% → L2 Glance (incremental parse)
       - diff ≥ 15% → L3 full pipeline
    3. Safety: any error at lower level → escalate to next

    Args:
        action_result: The action command's output dict, or None for standalone look.
        force_level: Override to skip decision logic ("L1", "L2", or "L3").

    Returns:
        SchedulerResult with perception output and metadata.
    """
    t0 = time.perf_counter_ns()
    escalation: list[str] = []
    timing: dict[str, object] = {}

    # Load persisted state
    t = time.perf_counter_ns()
    state = ContextState.load()
    timing["state_load_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    # Record the action that triggered this perception (if any)
    if action_result is not None and state is not None and action_result.get("action"):
        params = {k: v for k, v in action_result.items() if k not in ("status", "action")}
        state.record_action(action_result["action"], params)

    # Wait for screen to settle after action (e.g. menu opening, form submitting)
    t = time.perf_counter_ns()
    if action_result is not None and CONTEXT_POST_ACTION_DELAY > 0:
        time.sleep(CONTEXT_POST_ACTION_DELAY)
    timing["post_action_delay_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    # Take a screenshot for comparison
    t = time.perf_counter_ns()
    screen = take_screenshot()
    screenshot_path = screen["image_path"]
    screenshot_ts = screen.get("timestamp", 0)
    timing["screenshot_ms"] = (time.perf_counter_ns() - t) // 1_000_000
    if "timing" in screen:
        timing["screenshot"] = screen["timing"]

    # ── Force L3 conditions ──
    if state is None or force_level == "L3":
        if state is None:
            state = ContextState()
        return _run_full(screenshot_path, state, timing=timing, timestamp=screenshot_ts)

    if force_level == "L2":
        # Run L2 glance if we have state, otherwise fall through to L3
        peek_result = peek(state, screenshot_path)
        if peek_result.change_regions:
            try:
                glance_result = glance(screenshot_path, peek_result.change_regions, state)
                result_dict = glance_result.pipeline_result.to_dict()
                result_dict["_perception"] = {
                    "level": "L2",
                    "changed": True,
                    "diff_ratio": peek_result.diff_ratio,
                    "merged_from_cache": glance_result.merged_from_cache,
                    "newly_parsed": glance_result.newly_parsed,
                    "elapsed_ms": glance_result.elapsed_ms,
                }
                state.record_perception(
                    "L2",
                    result_dict=result_dict,
                    screenshot_path=screenshot_path,
                    elements=_elements_to_dicts(glance_result.pipeline_result.elements),
                    resolution=glance_result.pipeline_result.resolution,
                )
                state.save()
                elapsed = (time.perf_counter_ns() - t0) // 1_000_000
                return SchedulerResult(
                    level="L2", perception=result_dict, diff_ratio=peek_result.diff_ratio,
                    escalation_path=["L2"], elapsed_ms=elapsed,
                    timestamp=screenshot_ts, timing=timing,
                )
            except Exception:
                pass
        # Glance failed or no regions → fall back to L3
        return _run_full(screenshot_path, state, timing=timing, timestamp=screenshot_ts)

    if state.consecutive_cheap_count >= CONTEXT_MAX_CONSECUTIVE_CHEAP:
        return _run_full(screenshot_path, state, timing=timing, timestamp=screenshot_ts)

    if state.is_stale():
        return _run_full(screenshot_path, state, timing=timing, timestamp=screenshot_ts)

    # ── Force L1 ──
    if force_level == "L1":
        t = time.perf_counter_ns()
        peek_result = peek(state, screenshot_path)
        timing["peek_ms"] = (time.perf_counter_ns() - t) // 1_000_000
        result_dict = {
            "level": "L1",
            "changed": peek_result.changed,
            "diff_ratio": peek_result.diff_ratio,
            "change_regions": peek_result.change_regions,
            "elapsed_ms": peek_result.elapsed_ms,
        }
        state.record_perception("L1", screenshot_path=screenshot_path)
        state.save()
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        return SchedulerResult(
            level="L1", perception=result_dict, diff_ratio=peek_result.diff_ratio,
            escalation_path=["L1"], elapsed_ms=elapsed,
            timestamp=screenshot_ts, timing=timing,
        )

    # ── Automatic decision flow: always peek first ──

    # L1: Peek (pixel diff — the sole decision maker)
    escalation.append("L1")
    try:
        t = time.perf_counter_ns()
        peek_result = peek(state, screenshot_path)
        timing["peek_ms"] = (time.perf_counter_ns() - t) // 1_000_000
    except Exception:
        # Peek failed → escalate to L3
        return _run_full(screenshot_path, state, escalation=list(escalation), timing=timing, timestamp=screenshot_ts)

    if not peek_result.changed:
        # No change → return cache
        cached = state.last_result_dict or {}
        state.record_perception("L1", screenshot_path=screenshot_path)
        state.save()
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        result_dict = dict(cached)
        result_dict["_perception"] = {
            "level": "L1",
            "changed": False,
            "diff_ratio": peek_result.diff_ratio,
            "elapsed_ms": elapsed,
        }
        return SchedulerResult(
            level="L1", perception=result_dict, diff_ratio=peek_result.diff_ratio,
            escalation_path=list(escalation), elapsed_ms=elapsed,
            timestamp=screenshot_ts, timing=timing,
        )

    # L2: Glance or full pipeline based on diff ratio
    if peek_result.suggest_level == "L2" and peek_result.change_regions:
        escalation.append("L2")
        try:
            glance_result = glance(screenshot_path, peek_result.change_regions, state)
            result_dict = glance_result.pipeline_result.to_dict()
            result_dict["_perception"] = {
                "level": "L2",
                "changed": True,
                "diff_ratio": peek_result.diff_ratio,
                "merged_from_cache": glance_result.merged_from_cache,
                "newly_parsed": glance_result.newly_parsed,
                "elapsed_ms": glance_result.elapsed_ms,
            }
            state.record_perception(
                "L2",
                result_dict=result_dict,
                screenshot_path=screenshot_path,
                elements=_elements_to_dicts(glance_result.pipeline_result.elements),
                resolution=glance_result.pipeline_result.resolution,
            )
            state.save()
            elapsed = (time.perf_counter_ns() - t0) // 1_000_000
            return SchedulerResult(
                level="L2", perception=result_dict, diff_ratio=peek_result.diff_ratio,
                escalation_path=list(escalation), elapsed_ms=elapsed,
                timestamp=screenshot_ts, timing=timing,
            )
        except Exception as exc:
            logger.warning("Glance failed, falling back to full pipeline: %s", exc)

    # Full pipeline
    return _run_full(screenshot_path, state, escalation=list(escalation), timing=timing, timestamp=screenshot_ts)
