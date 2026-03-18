"""Tests for the smart perception scheduler."""

import time
from unittest.mock import patch, MagicMock

from xclaw.core.context.state import ContextState
from xclaw.core.context.predict import PredictResult
from xclaw.core.context.peek import PeekResult
from xclaw.core.context.glance import GlanceResult
from xclaw.core.pipeline import PipelineResult
from xclaw.core.perception.types import RawElement
from xclaw.core.context.scheduler import schedule, _run_full, SchedulerResult


def _elem(id=0, bbox=(0, 0, 10, 10), content="test"):
    return RawElement(
        id=id, type="text", bbox=bbox,
        center=((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2),
        content=content,
    )


def _make_pipeline_result(**kwargs):
    defaults = dict(
        elements=[_elem()],
        resolution=(1920, 1080),
        image_path="test.png",
        columns=[], reading_order=[],
        timing={"l1_ms": 100},
    )
    defaults.update(kwargs)
    return PipelineResult(**defaults)


def _mock_state(tmp_path, monkeypatch, **overrides):
    """Create a state and mock CONTEXT_STATE_PATH."""
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


class TestScheduleForceL2:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_no_state_forces_l2(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        state_path = tmp_path / ".context_state.json"
        monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)

        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "click", "x": 100, "y": 200})
        assert result.level == "L2"
        mock_pipeline.assert_called_once()

    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_force_level_l2(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        _mock_state(tmp_path, monkeypatch)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "click"}, force_level="L2")
        assert result.level == "L2"


class TestScheduleL0:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    def test_high_confidence_returns_cache(self, mock_peek, mock_screen, tmp_path, monkeypatch):
        """When confidence > 0.8 after type, L0 should return cache."""
        state = _mock_state(tmp_path, monkeypatch, confidence=1.0)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}

        result = schedule({"status": "ok", "action": "type", "text": "a"})
        assert result.level == "L0"
        assert result.confidence > 0.8
        mock_peek.assert_not_called()


class TestScheduleL1:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    def test_no_change_returns_cache(self, mock_peek, mock_screen, tmp_path, monkeypatch):
        """Click → confidence 0.75 → L1 peek → no change → return cache."""
        _mock_state(tmp_path, monkeypatch, confidence=1.0)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_peek.return_value = PeekResult(
            changed=False, diff_ratio=0.005, change_regions=[],
            screenshot_path="screen.png", elapsed_ms=40,
        )

        result = schedule({"status": "ok", "action": "click", "x": 100, "y": 200})
        assert result.level == "L1"
        assert "L0" in result.escalation_path
        assert "L1" in result.escalation_path


class TestScheduleL2:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    @patch("xclaw.core.context.scheduler.glance")
    def test_minor_change_triggers_glance(self, mock_glance, mock_peek, mock_screen, tmp_path, monkeypatch):
        """Click → peek shows minor change → L2 glance."""
        _mock_state(tmp_path, monkeypatch, confidence=1.0)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_peek.return_value = PeekResult(
            changed=True, diff_ratio=0.08, change_regions=[(100, 100, 200, 200)],
            screenshot_path="screen.png", elapsed_ms=40,
            suggest_level="L2",
        )
        mock_glance.return_value = GlanceResult(
            pipeline_result=_make_pipeline_result(),
            merged_from_cache=5,
            newly_parsed=2,
            elapsed_ms=300,
        )

        result = schedule({"status": "ok", "action": "click", "x": 100, "y": 200})
        assert result.level == "L2"
        assert "L2" in result.escalation_path
        mock_glance.assert_called_once()


class TestScheduleForceL1:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    def test_force_l1_path(self, mock_peek, mock_screen, tmp_path, monkeypatch):
        """force_level=L1 should run peek and return L1."""
        _mock_state(tmp_path, monkeypatch, confidence=1.0)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_peek.return_value = PeekResult(
            changed=False, diff_ratio=0.005, change_regions=[],
            screenshot_path="screen.png", elapsed_ms=30,
        )

        result = schedule({"status": "ok", "action": "click", "x": 1, "y": 2}, force_level="L1")
        assert result.level == "L1"
        assert result.escalation_path == ["L1"]
        mock_peek.assert_called_once()


class TestScheduleForceL2NoChange:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_force_l2_runs_full_pipeline(self, mock_pipeline, mock_screen, tmp_path, monkeypatch):
        """force_level=L2 should always run full pipeline."""
        _mock_state(tmp_path, monkeypatch, confidence=1.0)
        mock_screen.return_value = {"image_path": "screen.png", "resolution": [1920, 1080]}
        mock_pipeline.return_value = _make_pipeline_result()

        result = schedule({"status": "ok", "action": "type", "text": "a"}, force_level="L2")
        assert result.level == "L2"


class TestEscalationPathCorrectness:
    @patch("xclaw.core.context.scheduler.take_screenshot")
    @patch("xclaw.core.context.scheduler.peek")
    @patch("xclaw.core.context.scheduler.glance")
    @patch("xclaw.core.context.scheduler.run_pipeline")
    def test_full_escalation_l0_l1_l2(self, mock_pipeline, mock_glance, mock_peek, mock_screen, tmp_path, monkeypatch):
        """L0→L1→L2 glance fail → L2 full pipeline should have escalation path."""
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
        assert "L0" in result.escalation_path
        assert "L1" in result.escalation_path
        assert "L2" in result.escalation_path
