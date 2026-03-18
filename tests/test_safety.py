"""Tests for scheduler safety mechanisms."""

import time
from unittest.mock import patch

from xclaw.core.context.state import ContextState
from xclaw.core.context.peek import PeekResult
from xclaw.core.context.glance import GlanceResult
from xclaw.core.pipeline import PipelineResult
from xclaw.core.perception.types import RawElement
from xclaw.core.context.scheduler import schedule


def _elem(id=0, bbox=(0, 0, 10, 10), content="test"):
    return RawElement(
        id=id, type="text", bbox=bbox,
        center=((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2),
        content=content,
    )


def _make_pipeline_result(**kwargs):
    defaults = dict(
        elements=[_elem()], resolution=(1920, 1080), image_path="test.png",
        columns=[], reading_order=[],
        timing={"l1_ms": 100},
    )
    defaults.update(kwargs)
    return PipelineResult(**defaults)


def _mock_state(tmp_path, monkeypatch, **overrides):
    state_path = tmp_path / ".context_state.json"
    monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)
    defaults = dict(
        last_screenshot_path="prev.png",
        last_result_dict={"timing": {"l1_ms": 100}},
        last_perception_level="L2",
        last_perception_time=time.time() - 1,
        cached_elements=[],
        cached_resolution=(1920, 1080),
        confidence=1.0,
    )
    defaults.update(overrides)
    state = ContextState(**defaults)
    state.save()
    return state


class TestSafetyCriticalAction:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_enter_forces_l2(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        """Press enter should force L2 regardless of confidence."""
        state = _mock_state(tmp_path, monkeypatch, confidence=1.0)
        state.record_action("press", {"key": "enter"})
        state.save()

        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "press", "key": "enter"})
        assert result.level == "L2"

    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_f5_forces_l2(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        state = _mock_state(tmp_path, monkeypatch, confidence=1.0)
        state.record_action("press", {"key": "f5"})
        state.save()

        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "press", "key": "f5"})
        assert result.level == "L2"


class TestSafetyConsecutiveCheap:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_max_consecutive_forces_l2(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        """After 4 consecutive cheap perceptions, 5th should force L2."""
        state = _mock_state(
            tmp_path, monkeypatch,
            confidence=1.0,
            consecutive_cheap_count=4,
        )
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "type", "text": "a"})
        assert result.level == "L2"


class TestSafetyStaleCache:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_stale_cache_forces_l2(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        """Cache older than 15s should force L2."""
        state = _mock_state(
            tmp_path, monkeypatch,
            confidence=1.0,
            last_perception_time=time.time() - 20,
        )
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "type", "text": "a"})
        assert result.level == "L2"


class TestSafetyEscalation:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_peek_error_escalates_to_l2(self, mock_pipeline, mock_peek, mock_screen, tmp_path, monkeypatch):
        """If peek() raises, scheduler should escalate to L2."""
        _mock_state(tmp_path, monkeypatch, confidence=0.7)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_peek.side_effect = RuntimeError("cv2 failure")
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "click", "x": 1, "y": 2})
        assert result.level == "L2"

    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    @patch("xclaw.core.context.scheduler.glance")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_glance_error_escalates_to_l2(self, mock_pipeline, mock_glance, mock_peek, mock_screen, tmp_path, monkeypatch):
        """If glance() raises, scheduler should escalate to L2."""
        _mock_state(tmp_path, monkeypatch, confidence=0.7)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_peek.return_value = PeekResult(
            changed=True, diff_ratio=0.08, change_regions=[(100, 100, 200, 200)],
            screenshot_path="screen.png", elapsed_ms=40,
            suggest_level="L2",
        )
        mock_glance.side_effect = RuntimeError("glance failure")
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "click", "x": 1, "y": 2})
        assert result.level == "L2"


class TestSafetyStateSaveFailure:
    @patch("xclaw.core.context.state.os.replace")
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_save_failure_still_returns_result(self, mock_pipeline, mock_screen, mock_replace, tmp_path, monkeypatch):
        """If state.save() raises OSError, scheduler should still return a result."""
        state = _mock_state(tmp_path, monkeypatch, confidence=1.0)

        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()
        mock_replace.side_effect = OSError("disk full")

        result = schedule({"status": "ok", "action": "press", "key": "enter"})
        assert result.level == "L2"
        assert result.perception is not None

    @patch("xclaw.core.context.scheduler.take_screenshot")
    def test_screenshot_failure_propagates(self, mock_screen, tmp_path, monkeypatch):
        """If take_screenshot raises, schedule should propagate the error."""
        _mock_state(tmp_path, monkeypatch, confidence=1.0)
        mock_screen.side_effect = RuntimeError("monitor not found")

        import pytest
        with pytest.raises(RuntimeError, match="monitor not found"):
            schedule({"status": "ok", "action": "click", "x": 1, "y": 2})
