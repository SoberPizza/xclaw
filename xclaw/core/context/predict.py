"""L0 Predict — confidence decay based on action history."""

from __future__ import annotations

from dataclasses import dataclass

from xclaw.core.context.state import ContextState, parse_base_key
from xclaw.config import CONTEXT_CONFIDENCE_L0, CONTEXT_CONFIDENCE_L1, CONTEXT_CONFIDENCE_L2


# Decay coefficients: how much each action reduces confidence
DECAY_TABLE: dict[str, float] = {
    "type": 0.95,
    "wait": 1.0,
    "press:escape": 0.85,
    "click": 0.75,
    "click:unknown": 0.4,
    "scroll": 0.6,
    "press:enter": 0.3,
    "press:f5": 0.1,
}

# Default decay for unrecognized press keys
_PRESS_DEFAULT_DECAY = 0.7


def _decay_for_action(action: str, params: dict) -> float:
    """Look up the decay coefficient for a given action + params."""
    if action == "press":
        key = params.get("key", "").lower()
        base_key = parse_base_key(key)
        specific = f"press:{base_key}"
        if specific in DECAY_TABLE:
            return DECAY_TABLE[specific]
        return _PRESS_DEFAULT_DECAY
    return DECAY_TABLE.get(action, 0.5)


@dataclass
class PredictResult:
    """Result of L0 confidence prediction."""

    confidence: float
    suggest_level: str  # "L0" | "L1" | "L2" | "L3"
    cached_result: dict | None  # returned when confidence is high enough


def predict(state: ContextState) -> PredictResult:
    """Predict required perception level from action history and confidence.

    Starting from the stored confidence (set to 1.0 after an L3 perception),
    apply decay for each action recorded since the last perception.
    """
    if state.last_perception_time is None:
        return PredictResult(confidence=0.0, suggest_level="L3", cached_result=None)

    confidence = state.confidence

    # Find actions after the last perception
    actions_since = [
        a for a in state.action_history
        if a.timestamp > (state.last_perception_time or 0)
    ]

    for a in actions_since:
        decay = _decay_for_action(a.action, a.params)
        confidence *= decay

    confidence = max(0.0, min(1.0, confidence))

    # Map confidence to suggested level
    if confidence > CONTEXT_CONFIDENCE_L0:
        level = "L0"
    elif confidence > CONTEXT_CONFIDENCE_L1:
        level = "L1"
    elif confidence > CONTEXT_CONFIDENCE_L2:
        level = "L2"
    else:
        level = "L3"

    cached = state.last_result_dict if level == "L0" else None

    return PredictResult(confidence=confidence, suggest_level=level, cached_result=cached)
