"""Tests for L0 predict — confidence decay."""

import time

from xclaw.core.context.state import ContextState
from xclaw.core.context.predict import predict, _decay_for_action, PredictResult


class TestDecayForAction:
    def test_type_decay(self):
        assert _decay_for_action("type", {"text": "hi"}) == 0.95

    def test_wait_no_decay(self):
        assert _decay_for_action("wait", {"seconds": 1}) == 1.0

    def test_click_decay(self):
        assert _decay_for_action("click", {"x": 1, "y": 2}) == 0.75

    def test_scroll_decay(self):
        assert _decay_for_action("scroll", {"direction": "down"}) == 0.6

    def test_press_enter_decay(self):
        assert _decay_for_action("press", {"key": "enter"}) == 0.3

    def test_press_f5_decay(self):
        assert _decay_for_action("press", {"key": "f5"}) == 0.1

    def test_press_escape_decay(self):
        assert _decay_for_action("press", {"key": "escape"}) == 0.85

    def test_press_ctrl_enter(self):
        assert _decay_for_action("press", {"key": "ctrl+enter"}) == 0.3

    def test_press_unknown_key(self):
        assert _decay_for_action("press", {"key": "tab"}) == 0.7

    def test_unknown_action_fallback(self):
        assert _decay_for_action("unknown_action", {}) == 0.5


class TestPredict:
    def test_no_perception_suggests_l3(self):
        state = ContextState()
        result = predict(state)
        assert result.confidence == 0.0
        assert result.suggest_level == "L3"
        assert result.cached_result is None

    def test_high_confidence_after_type(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now - 1,
            last_result_dict={"test": True},
        )
        state.record_action("type", {"text": "a"})
        # Confidence: 1.0 * 0.95 = 0.95 → L0
        result = predict(state)
        assert result.confidence > 0.8
        assert result.suggest_level == "L0"
        assert result.cached_result == {"test": True}

    def test_medium_confidence_after_click(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now - 1,
        )
        state.record_action("click", {"x": 100, "y": 200})
        # Confidence: 1.0 * 0.75 = 0.75 → L1
        result = predict(state)
        assert 0.5 < result.confidence <= 0.8
        assert result.suggest_level == "L1"
        assert result.cached_result is None

    def test_low_confidence_after_scroll(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now - 1,
        )
        state.record_action("scroll", {"direction": "down", "amount": 3})
        # Confidence: 1.0 * 0.6 = 0.6 → L1
        result = predict(state)
        assert result.suggest_level == "L1"

    def test_very_low_after_enter(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now - 1,
        )
        state.record_action("press", {"key": "enter"})
        # Confidence: 1.0 * 0.3 = 0.3 → L3
        result = predict(state)
        assert result.confidence <= 0.3
        assert result.suggest_level == "L3"

    def test_cumulative_decay(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now - 1,
        )
        # 3 type actions: 1.0 * 0.95^3 ≈ 0.857 → L0
        state.record_action("type", {"text": "a"})
        state.record_action("type", {"text": "b"})
        state.record_action("type", {"text": "c"})
        result = predict(state)
        assert result.suggest_level == "L0"
        assert abs(result.confidence - 0.95**3) < 0.01

    def test_wait_preserves_confidence(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now - 1,
        )
        state.record_action("wait", {"seconds": 2})
        result = predict(state)
        assert result.confidence == 1.0
        assert result.suggest_level == "L0"

    def test_only_counts_actions_after_perception(self):
        now = time.time()
        state = ContextState(
            confidence=1.0,
            last_perception_time=now,  # perception happened at `now`
        )
        # Action before perception time → should be ignored
        state.action_history = []
        from xclaw.core.context.state import ActionRecord
        state.action_history.append(
            ActionRecord(action="press", params={"key": "enter"}, timestamp=now - 5)
        )
        # Action after perception time
        state.action_history.append(
            ActionRecord(action="type", params={"text": "a"}, timestamp=now + 1)
        )
        result = predict(state)
        # Only the type action counts: 1.0 * 0.95 = 0.95
        assert abs(result.confidence - 0.95) < 0.01
