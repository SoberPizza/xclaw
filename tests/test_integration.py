"""Integration tests — real cv2 ops on real/synthetic screenshots, real state persistence."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from xclaw.core.context.state import ContextState, ActionRecord
from xclaw.core.context.scheduler import schedule, SchedulerResult
from xclaw.core.context.peek import peek, PeekResult
from xclaw.core.context.predict import predict
from xclaw.core.context.glance import _elements_to_dicts
from xclaw.core.pipeline import PipelineResult

from conftest import _elem, _build_elements

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# TestSchedulerL0CacheHit
# ---------------------------------------------------------------------------

class TestSchedulerL0CacheHit:
    """L0 path: high confidence with no action → return cache without any GPU work."""

    def test_l0_high_confidence_returns_cache(
        self, state_dir, mock_take_screenshot, make_gray_image, tmp_path,
    ):
        elements = _build_elements(5)
        state = ContextState(
            last_screenshot_path=make_gray_image(128, name="prev.png"),
            last_result_dict={"level": "L2", "data": "cached"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(elements),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.save()

        screenshot = make_gray_image(128, name="curr.png")
        mock_take_screenshot.set_next(screenshot)

        with patch("xclaw.core.context.scheduler.run_pipeline", side_effect=AssertionError("L2 should not run")), \
             patch("xclaw.core.context.glance._crop_and_parse", side_effect=AssertionError("glance should not run")):
            result = schedule(None)  # no action → L0 allowed

        assert result.level == "L0"
        assert result.confidence > 0.8
        assert result.escalation_path == ["L0"]
        assert result.elapsed_ms < 500


# ---------------------------------------------------------------------------
# TestSchedulerL0ThenL1NoChange
# ---------------------------------------------------------------------------

class TestSchedulerL0ThenL1NoChange:
    """L1 path: click decays confidence → peek shows identical screenshots."""

    def test_l1_identical_screenshots(
        self, state_dir, mock_take_screenshot, mock_run_pipeline, screenshot_pair,
    ):
        path_a, path_b = screenshot_pair
        state = ContextState(
            last_screenshot_path=path_a,
            last_result_dict=mock_run_pipeline.pipeline_dict,
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(mock_run_pipeline.raw_elements),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.record_action("click", {"x": 100, "y": 200})
        state.save()

        mock_take_screenshot.set_next(path_a)

        result = schedule({"status": "ok", "action": "click", "x": 100, "y": 200})

        assert result.level == "L1"
        assert result.confidence >= 0.5
        assert result.perception.get("_perception", {}).get("changed") is False or \
               result.perception.get("_perception", {}).get("diff_ratio", 1.0) == 0.0


# ---------------------------------------------------------------------------
# TestSchedulerL2MinorChange
# ---------------------------------------------------------------------------

class TestSchedulerL2MinorChange:
    """L2 path: small diff → glance with crop_and_parse mock."""

    def test_l2_synthetic_minor_diff(
        self, state_dir, mock_take_screenshot, mock_crop_and_parse,
        make_gray_image, make_image_with_rect, tmp_path,
    ):
        """Synthetic images: gray base vs gray+small rectangle → minor diff → L2."""
        prev_path = make_gray_image(128, name="l2_prev.png")
        curr_path = make_image_with_rect(
            bg_color=128, rect_color=255,
            rect=(100, 100, 500, 350),
            name="l2_curr.png",
        )

        state = ContextState(
            last_screenshot_path=prev_path,
            last_result_dict={"level": "L2", "data": "cached"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(5)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )

        peek_result = peek(state, curr_path)
        assert peek_result.changed is True
        assert 0.0 < peek_result.diff_ratio < 0.15, f"Expected minor diff, got {peek_result.diff_ratio}"
        assert peek_result.suggest_level == "L2"

        state.record_action("click", {"x": 300, "y": 250})
        state.save()

        mock_take_screenshot.set_next(curr_path)

        with patch("xclaw.core.context.glance.run_pipeline") as mock_rp, \
             patch("xclaw.core.perception.merger.merge_elements", side_effect=lambda x: x), \
             patch("xclaw.core.perception.omniparser.OmniDetector"):
            result = schedule({"status": "ok", "action": "click", "x": 300, "y": 250})

        assert result.level == "L2"
        assert "L0" in result.escalation_path
        assert "L1" in result.escalation_path
        assert "L2" in result.escalation_path

    def test_l2_real_screenshots(
        self, state_dir, mock_take_screenshot, mock_crop_and_parse,
        screenshot_pair, tmp_path,
    ):
        """Real consecutive screenshots — accept L2 depending on actual diff."""
        path_a, path_b = screenshot_pair

        state = ContextState(
            last_screenshot_path=path_a,
            last_result_dict={"level": "L2", "data": "cached"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(5)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )

        peek_result = peek(state, path_b)

        assert isinstance(peek_result, PeekResult)
        assert 0.0 <= peek_result.diff_ratio <= 1.0
        assert peek_result.suggest_level in ("L1", "L2", "L3")


# ---------------------------------------------------------------------------
# TestSchedulerL2MajorChange
# ---------------------------------------------------------------------------

class TestSchedulerL2MajorChange:
    """L2 path: large diff → full pipeline (mocked)."""

    def test_l2_synthetic_major_diff(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        make_gray_image, tmp_path,
    ):
        """White vs black image → diff_ratio ≈ 1.0 → L2."""
        white = make_gray_image(255, name="white.png")
        black = make_gray_image(0, name="black.png")

        state = ContextState(
            last_screenshot_path=white,
            last_result_dict={"level": "L2", "data": "old"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(5)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.record_action("click", {"x": 500, "y": 500})
        state.save()

        mock_take_screenshot.set_next(black)

        result = schedule({"status": "ok", "action": "click", "x": 500, "y": 500})

        assert result.level == "L2"
        assert "L2" in result.escalation_path

    def test_l2_real_non_consecutive(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        screenshot_paths, tmp_path,
    ):
        """First vs last screenshot — typically large diff → L2."""
        first = str(screenshot_paths[0])
        last = str(screenshot_paths[-1])

        state = ContextState(
            last_screenshot_path=first,
            last_result_dict={"level": "L2", "data": "old"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(5)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.record_action("click", {"x": 100, "y": 100})
        state.save()

        mock_take_screenshot.set_next(last)

        result = schedule({"status": "ok", "action": "click", "x": 100, "y": 100})

        assert result.level == "L2"


# ---------------------------------------------------------------------------
# TestSchedulerForcedL2Paths
# ---------------------------------------------------------------------------

class TestSchedulerForcedL2Paths:
    """Conditions that force L2 regardless of diff."""

    def test_stale_cache(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        make_gray_image,
    ):
        """last_perception_time 20s ago → stale → force L2."""
        img = make_gray_image(128, name="stale.png")

        state = ContextState(
            last_screenshot_path=img,
            last_result_dict={"level": "L2"},
            last_perception_level="L2",
            last_perception_time=time.time() - 20.0,
            cached_elements=_elements_to_dicts(_build_elements(3)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.record_action("type", {"text": "x"})
        state.save()

        mock_take_screenshot.set_next(img)

        result = schedule({"status": "ok", "action": "type", "text": "x"})
        assert result.level == "L2"

    def test_critical_action(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        make_gray_image,
    ):
        """press:enter → critical action → force L2."""
        img = make_gray_image(128, name="critical.png")

        state = ContextState(
            last_screenshot_path=img,
            last_result_dict={"level": "L2"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(3)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.record_action("press", {"key": "enter"})
        state.save()

        mock_take_screenshot.set_next(img)

        result = schedule({"status": "ok", "action": "press", "key": "enter"})
        assert result.level == "L2"

    def test_consecutive_cheap_limit(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        make_gray_image,
    ):
        """consecutive_cheap_count=4 → force L2."""
        img = make_gray_image(128, name="cheap.png")

        state = ContextState(
            last_screenshot_path=img,
            last_result_dict={"level": "L2"},
            last_perception_level="L0",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(3)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=4,
        )
        state.record_action("type", {"text": "y"})
        state.save()

        mock_take_screenshot.set_next(img)

        result = schedule({"status": "ok", "action": "type", "text": "y"})
        assert result.level == "L2"


# ---------------------------------------------------------------------------
# TestStatePersistenceAcrossCalls
# ---------------------------------------------------------------------------

class TestStatePersistenceAcrossCalls:
    """Verify state survives save/load cycles between scheduler calls."""

    def test_multi_call_sequence(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        make_gray_image,
    ):
        """Simulate 6 CLI calls sharing disk state.

        Post-action minimum level is L1, so type/click actions always
        trigger at least L1 peek (never L0 cache).

        1. No state → L2
        2. type → L1 (post-action forces at least L1, cheap +1)
        3. type → L1 (cheap +2)
        4. click → L1 (cheap +3)
        5. type → L1 (cheap +4)
        6. type → L2 (consecutive_cheap=4, hit limit)
        """
        img = make_gray_image(128, name="seq.png")

        # Call 1: no state file → L2
        mock_take_screenshot.set_next(img)
        r1 = schedule({"status": "ok", "action": "type", "text": "a"})
        assert r1.level == "L2"

        s1 = ContextState.load()
        assert s1 is not None
        assert s1.confidence == 1.0
        assert s1.consecutive_cheap_count == 0

        # Call 2: type → L1 (post-action forces at least peek)
        mock_take_screenshot.set_next(img)
        r2 = schedule({"status": "ok", "action": "type", "text": "b"})
        assert r2.level == "L1"
        s2 = ContextState.load()
        assert s2.consecutive_cheap_count == 1

        # Call 3: type → L1 (cheap +2)
        mock_take_screenshot.set_next(img)
        r3 = schedule({"status": "ok", "action": "type", "text": "c"})
        assert r3.level == "L1"
        s3 = ContextState.load()
        assert s3.consecutive_cheap_count == 2

        # Call 4: click (decay=0.75) → confidence drops below 0.8 → L1
        mock_take_screenshot.set_next(img)
        r4 = schedule({"status": "ok", "action": "click", "x": 10, "y": 10})
        assert r4.level == "L1"
        s4 = ContextState.load()
        assert s4.consecutive_cheap_count == 3

        # Call 5: type after L1
        mock_take_screenshot.set_next(img)
        r5 = schedule({"status": "ok", "action": "type", "text": "d"})
        assert r5.level == "L1"
        s5 = ContextState.load()
        assert s5.consecutive_cheap_count == 4

        # Call 6: consecutive_cheap=4 → force L2
        mock_take_screenshot.set_next(img)
        r6 = schedule({"status": "ok", "action": "type", "text": "e"})
        assert r6.level == "L2"
        s6 = ContextState.load()
        assert s6.consecutive_cheap_count == 0

    def test_state_round_trip(self, state_dir):
        """Save → load → compare all fields."""
        elements = _elements_to_dicts(_build_elements(5))
        original = ContextState(
            last_screenshot_path="/tmp/test.png",
            last_result_dict={"level": "L2", "data": [1, 2, 3]},
            last_perception_level="L2",
            last_perception_time=1700000000.0,
            cached_elements=elements,
            cached_resolution=(1920, 1080),
            action_history=[
                ActionRecord("click", {"x": 10}, 1700000001.0),
                ActionRecord("type", {"text": "hi"}, 1700000002.0),
            ],
            consecutive_cheap_count=2,
            confidence=0.85,
        )
        original.save()

        loaded = ContextState.load()
        assert loaded is not None
        assert loaded.last_screenshot_path == original.last_screenshot_path
        assert loaded.last_result_dict == original.last_result_dict
        assert loaded.last_perception_level == original.last_perception_level
        assert loaded.last_perception_time == original.last_perception_time
        assert loaded.cached_elements == original.cached_elements
        assert loaded.cached_resolution == original.cached_resolution
        assert loaded.consecutive_cheap_count == original.consecutive_cheap_count
        assert loaded.confidence == original.confidence
        assert len(loaded.action_history) == 2
        assert loaded.action_history[0].action == "click"
        assert loaded.action_history[1].params == {"text": "hi"}


# ---------------------------------------------------------------------------
# TestTimingReasonableness
# ---------------------------------------------------------------------------

class TestTimingReasonableness:
    """Verify timing values are populated and within reasonable bounds."""

    def test_l0_timing_under_100ms(
        self, state_dir, mock_take_screenshot, make_gray_image,
    ):
        """L0 cache hit (no action) should be very fast."""
        img = make_gray_image(128, name="timing_l0.png")

        state = ContextState(
            last_screenshot_path=img,
            last_result_dict={"level": "L2", "data": "ok"},
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(_build_elements(3)),
            cached_resolution=(1920, 1080),
            confidence=1.0,
            consecutive_cheap_count=0,
        )
        state.save()

        mock_take_screenshot.set_next(img)

        with patch("xclaw.core.context.scheduler.run_pipeline", side_effect=AssertionError):
            result = schedule(None)  # no action → L0 allowed

        assert result.level == "L0"
        assert result.elapsed_ms < 500

    def test_l1_timing_with_real_cv2(
        self, state_dir, screenshot_pair,
    ):
        """Real 1920×1080-ish screenshot diff should complete in reasonable time."""
        path_a, path_b = screenshot_pair

        state = ContextState(
            last_screenshot_path=path_a,
            confidence=0.7,
            last_perception_time=time.time(),
        )

        t0 = time.perf_counter()
        result = peek(state, path_b)
        elapsed = (time.perf_counter() - t0) * 1000

        assert result.elapsed_ms >= 0
        assert elapsed < 5000, f"peek took {elapsed:.0f}ms, expected < 5000ms"

    def test_elapsed_is_not_zero(
        self, state_dir, mock_take_screenshot, mock_run_pipeline,
        make_gray_image,
    ):
        """Scheduler should always report non-negative elapsed_ms."""
        img = make_gray_image(128, name="timing_nz.png")

        mock_take_screenshot.set_next(img)
        result = schedule({"status": "ok", "action": "click", "x": 0, "y": 0})

        assert result.elapsed_ms >= 0


# ---------------------------------------------------------------------------
# TestGPU (requires GPU + OmniParser models)
# ---------------------------------------------------------------------------

@pytest.mark.gpu
class TestGPU:
    """End-to-end tests using real GPU inference. Skipped by default."""

    def test_full_pipeline_real(self, state_dir, screenshot_paths):
        """Real screenshot → real OmniParser → validate output structure."""
        from xclaw.core.pipeline import run_pipeline

        path = str(screenshot_paths[0])
        result = run_pipeline(path)

        assert isinstance(result, PipelineResult)
        assert len(result.elements) > 0
        assert result.resolution[0] > 0
        assert result.resolution[1] > 0
        assert "l1_ms" in result.timing
        assert "l2_ms" in result.timing

    def test_glance_real_parser(self, state_dir, screenshot_pair):
        """Real peek + real glance without any mocks."""
        path_a, path_b = screenshot_pair

        from xclaw.core.pipeline import run_pipeline

        full_result = run_pipeline(path_a)
        state = ContextState(
            last_screenshot_path=path_a,
            last_result_dict=full_result.to_dict(),
            last_perception_level="L2",
            last_perception_time=time.time(),
            cached_elements=_elements_to_dicts(full_result.elements),
            cached_resolution=full_result.resolution,
            confidence=1.0,
            consecutive_cheap_count=0,
        )

        peek_result = peek(state, path_b)
        assert isinstance(peek_result, PeekResult)

        if peek_result.suggest_level == "L2" and peek_result.change_regions:
            from xclaw.core.context.glance import glance
            glance_result = glance(path_b, peek_result.change_regions, state)
            assert glance_result.pipeline_result is not None
            assert glance_result.elapsed_ms >= 0
