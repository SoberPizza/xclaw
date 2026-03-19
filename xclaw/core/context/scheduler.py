"""Scheduler — orchestrates L0→L2 perception with safety mechanisms."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from xclaw.config import (
    CONTEXT_MAX_CONSECUTIVE_CHEAP,
    CONTEXT_POST_ACTION_DELAY,
    CONTEXT_POST_ACTION_MIN_LEVEL,
)
from xclaw.core.context.state import ContextState
from xclaw.core.context.predict import predict
from xclaw.core.context.peek import peek
from xclaw.core.context.glance import glance, _elements_to_dicts
from xclaw.core.screen import take_screenshot
from xclaw.core.pipeline import run_pipeline

logger = logging.getLogger(__name__)


@dataclass
class SchedulerResult:
    """Output of the scheduler."""

    level: str  # "L0" | "L1" | "L2"
    perception: dict  # perception output
    confidence: float
    escalation_path: list[str]  # e.g. ["L0", "L1", "L2"]
    elapsed_ms: int


def _run_full(screenshot_path: str, state: ContextState, escalation: list[str] | None = None) -> SchedulerResult:
    """Full L2 pipeline."""
    t0 = time.perf_counter_ns()
    result = run_pipeline(screenshot_path)
    result_dict = result.to_dict()

    state.record_perception(
        "L2",
        result_dict=result_dict,
        screenshot_path=screenshot_path,
        elements=_elements_to_dicts(result.elements),
        resolution=result.resolution,
    )
    state.confidence = 1.0
    state.save()

    elapsed = (time.perf_counter_ns() - t0) // 1_000_000
    path = (escalation or []) + ["L2"]
    return SchedulerResult(
        level="L2", perception=result_dict, confidence=1.0,
        escalation_path=path, elapsed_ms=elapsed,
    )


def schedule(
    action_result: dict | None = None,
    *,
    force_level: str | None = None,
) -> SchedulerResult:
    """Run the smart perception scheduler — the recommended entry point.

    This is the standard entry point for all perception calls in the agent
    loop.  For an uncached full pipeline run, pass ``force_level="L2"``.

    Decision flow:
    1. Force L2 if: no state, force_level="L2", critical action, too many cheap, stale cache
    2. L0 Predict: if confidence > 0.8 → return cache
    3. L1 Peek: pixel diff
       - diff < 1% → return cache
       - diff < 15% → L2 Glance
       - diff ≥ 15% → L2 full pipeline
    4. Safety: any error at lower level → escalate to next

    Args:
        action_result: The action command's output dict, or None for standalone look.
        force_level: Override to skip decision logic ("L1" or "L2").

    Returns:
        SchedulerResult with perception output and metadata.
    """
    t0 = time.perf_counter_ns()
    escalation: list[str] = []

    # Load persisted state
    state = ContextState.load()

    # Record the action that triggered this perception (if any)
    if action_result is not None and state is not None and action_result.get("action"):
        params = {k: v for k, v in action_result.items() if k not in ("status", "action")}
        state.record_action(action_result["action"], params)
        state.save()

    # Wait for screen to settle after action (e.g. menu opening, form submitting)
    if action_result is not None and CONTEXT_POST_ACTION_DELAY > 0:
        time.sleep(CONTEXT_POST_ACTION_DELAY)

    # Take a screenshot for comparison
    screen = take_screenshot()
    screenshot_path = screen["image_path"]

    # ── Force L2 conditions ──
    if state is None or force_level == "L2":
        if state is None:
            state = ContextState()
        return _run_full(screenshot_path, state)

    if action_result is not None and state.is_critical_action():
        return _run_full(screenshot_path, state)

    if state.consecutive_cheap_count >= CONTEXT_MAX_CONSECUTIVE_CHEAP:
        return _run_full(screenshot_path, state)

    if state.is_stale():
        return _run_full(screenshot_path, state)

    # ── Force specific level ──
    if force_level == "L1":
        peek_result = peek(state, screenshot_path)
        result_dict = {
            "level": "L1",
            "changed": peek_result.changed,
            "diff_ratio": peek_result.diff_ratio,
            "change_regions": peek_result.change_regions,
            "elapsed_ms": peek_result.elapsed_ms,
        }
        if not peek_result.changed and state.last_result_dict:
            result_dict["confidence"] = state.confidence
        state.record_perception("L1", screenshot_path=screenshot_path)
        state.save()
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        return SchedulerResult(
            level="L1", perception=result_dict, confidence=state.confidence,
            escalation_path=["L1"], elapsed_ms=elapsed,
        )

    # ── Automatic decision flow ──

    # L0: Predict
    escalation.append("L0")
    pred = predict(state)

    # After an action, skip L0 cache return — force at least L1 pixel verification
    post_action = action_result is not None and action_result.get("action")
    if (
        pred.suggest_level == "L0"
        and pred.cached_result is not None
        and not (post_action and CONTEXT_POST_ACTION_MIN_LEVEL >= "L1")
    ):
        state.record_perception("L0", screenshot_path=screenshot_path)
        state.confidence = pred.confidence
        state.save()
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        result_dict = dict(pred.cached_result)
        result_dict["_perception"] = {
            "level": "L0",
            "confidence": round(pred.confidence, 2),
            "elapsed_ms": elapsed,
        }
        return SchedulerResult(
            level="L0", perception=result_dict, confidence=pred.confidence,
            escalation_path=list(escalation), elapsed_ms=elapsed,
        )

    # L1: Peek
    escalation.append("L1")
    try:
        peek_result = peek(state, screenshot_path)
    except Exception:
        # Peek failed → escalate to L2
        return _run_full(screenshot_path, state, escalation=list(escalation))

    if not peek_result.changed:
        # No change → return cache
        cached = state.last_result_dict or {}
        state.record_perception("L1", screenshot_path=screenshot_path)
        state.confidence = max(pred.confidence, 0.5)
        state.save()
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        result_dict = dict(cached)
        result_dict["_perception"] = {
            "level": "L1",
            "confidence": round(state.confidence, 2),
            "changed": False,
            "diff_ratio": peek_result.diff_ratio,
            "elapsed_ms": elapsed,
        }
        return SchedulerResult(
            level="L1", perception=result_dict, confidence=state.confidence,
            escalation_path=list(escalation), elapsed_ms=elapsed,
        )

    # L2: Glance or full pipeline based on diff ratio
    if peek_result.suggest_level == "L2" and peek_result.change_regions:
        escalation.append("L2")
        try:
            glance_result = glance(screenshot_path, peek_result.change_regions, state)
            result_dict = glance_result.pipeline_result.to_dict()
            result_dict["_perception"] = {
                "level": "L2",
                "confidence": round(pred.confidence, 2),
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
                level="L2", perception=result_dict, confidence=state.confidence,
                escalation_path=list(escalation), elapsed_ms=elapsed,
            )
        except Exception as exc:
            logger.warning("Glance failed, falling back to full pipeline: %s", exc)

    # Full pipeline
    return _run_full(screenshot_path, state, escalation=list(escalation))
