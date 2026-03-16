"""Tests for ContextState persistence and mutation."""

import json
import time

from xclaw.core.context.state import ContextState, ActionRecord


class TestActionRecord:
    def test_round_trip(self):
        rec = ActionRecord(action="click", params={"x": 100, "y": 200}, timestamp=1000.0)
        d = rec.to_dict()
        restored = ActionRecord.from_dict(d)
        assert restored.action == "click"
        assert restored.params == {"x": 100, "y": 200}
        assert restored.timestamp == 1000.0

    def test_from_dict_defaults(self):
        rec = ActionRecord.from_dict({"action": "wait"})
        assert rec.params == {}
        assert rec.timestamp == 0.0


class TestContextStatePersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        state_path = tmp_path / ".context_state.json"
        monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)

        state = ContextState(
            last_screenshot_path="screenshots/screen_1.png",
            last_perception_level="L3",
            last_perception_time=1000.0,
            cached_resolution=(1920, 1080),
            confidence=0.85,
        )
        state.record_action("click", {"x": 100, "y": 200})
        state.save()

        assert state_path.exists()

        loaded = ContextState.load()
        assert loaded is not None
        assert loaded.last_screenshot_path == "screenshots/screen_1.png"
        assert loaded.last_perception_level == "L3"
        assert loaded.last_perception_time == 1000.0
        assert loaded.cached_resolution == (1920, 1080)
        assert loaded.confidence == 0.85
        assert len(loaded.action_history) == 1
        assert loaded.action_history[0].action == "click"

    def test_load_missing(self, tmp_path, monkeypatch):
        state_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)
        assert ContextState.load() is None

    def test_load_corrupt(self, tmp_path, monkeypatch):
        state_path = tmp_path / ".context_state.json"
        state_path.write_text("NOT JSON")
        monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)
        assert ContextState.load() is None

    def test_load_null_cached_resolution(self, tmp_path, monkeypatch):
        """cached_resolution: null in JSON should not crash."""
        state_path = tmp_path / ".context_state.json"
        monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)
        data = {
            "last_screenshot_path": None,
            "last_result_dict": None,
            "last_perception_level": None,
            "last_perception_time": None,
            "cached_elements": [],
            "cached_resolution": None,
            "action_history": [],
            "consecutive_cheap_count": 0,
            "confidence": 0.0,
        }
        state_path.write_text(json.dumps(data))
        loaded = ContextState.load()
        assert loaded is not None
        assert loaded.cached_resolution == (0, 0)


class TestRecordAction:
    def test_appends(self):
        state = ContextState()
        state.record_action("click", {"x": 1, "y": 2})
        state.record_action("type", {"text": "hi"})
        assert len(state.action_history) == 2
        assert state.action_history[0].action == "click"
        assert state.action_history[1].action == "type"

    def test_trims_to_10(self):
        state = ContextState()
        for i in range(15):
            state.record_action("click", {"x": i})
        assert len(state.action_history) == 10
        assert state.action_history[0].params["x"] == 5  # first 5 trimmed


class TestRecordPerception:
    def test_l3_resets_confidence(self):
        state = ContextState(confidence=0.3, consecutive_cheap_count=3)
        state.record_perception("L3", result_dict={"test": True})
        assert state.confidence == 1.0
        assert state.consecutive_cheap_count == 0
        assert state.last_perception_level == "L3"
        assert state.last_result_dict == {"test": True}

    def test_cheap_increments_counter(self):
        state = ContextState(consecutive_cheap_count=0)
        state.record_perception("L0")
        assert state.consecutive_cheap_count == 1
        state.record_perception("L1")
        assert state.consecutive_cheap_count == 2

    def test_l2_resets_counter(self):
        state = ContextState(consecutive_cheap_count=3)
        state.record_perception("L2")
        assert state.consecutive_cheap_count == 0


class TestIsStale:
    def test_no_perception_is_stale(self):
        state = ContextState()
        assert state.is_stale()

    def test_recent_not_stale(self):
        state = ContextState(last_perception_time=time.time())
        assert not state.is_stale()

    def test_old_is_stale(self):
        state = ContextState(last_perception_time=time.time() - 20.0)
        assert state.is_stale()


class TestIsCriticalAction:
    def test_no_history(self):
        state = ContextState()
        assert not state.is_critical_action()

    def test_enter_is_critical(self):
        state = ContextState()
        state.record_action("press", {"key": "enter"})
        assert state.is_critical_action()

    def test_f5_is_critical(self):
        state = ContextState()
        state.record_action("press", {"key": "f5"})
        assert state.is_critical_action()

    def test_ctrl_enter_is_critical(self):
        state = ContextState()
        state.record_action("press", {"key": "ctrl+enter"})
        assert state.is_critical_action()

    def test_tab_not_critical(self):
        state = ContextState()
        state.record_action("press", {"key": "tab"})
        assert not state.is_critical_action()

    def test_click_not_critical(self):
        state = ContextState()
        state.record_action("click", {"x": 100, "y": 200})
        assert not state.is_critical_action()
