"""Tests for L2 glance — local incremental parse."""

from unittest.mock import patch, MagicMock

from xclaw.core.perception.types import RawElement
from xclaw.core.context.state import ContextState
from xclaw.core.context.glance import (
    glance, _overlap_ratio, _elements_from_dicts, _elements_to_dicts,
    GlanceResult,
)


def _elem(id, type="text", bbox=(0, 0, 10, 10), content="test"):
    return RawElement(
        id=id, type=type, bbox=bbox,
        center=((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2),
        content=content,
    )


def _elem_to_dict(e: RawElement) -> dict:
    return {
        "id": e.id, "type": e.type,
        "bbox": list(e.bbox), "center": list(e.center),
        "content": e.content, "confidence": e.confidence,
        "source": e.source,
    }


class TestOverlapRatio:
    def test_no_overlap(self):
        assert _overlap_ratio((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0

    def test_full_overlap(self):
        assert _overlap_ratio((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_partial_overlap(self):
        ratio = _overlap_ratio((0, 0, 10, 10), (5, 5, 15, 15))
        # Intersection: 5x5=25, elem area: 100
        assert abs(ratio - 0.25) < 0.01

    def test_contained(self):
        ratio = _overlap_ratio((5, 5, 8, 8), (0, 0, 20, 20))
        assert ratio == 1.0

    def test_zero_area_elem(self):
        assert _overlap_ratio((5, 5, 5, 5), (0, 0, 10, 10)) == 0.0


class TestElementSerialization:
    def test_round_trip(self):
        elem = _elem(0, bbox=(10, 20, 30, 40), content="hello")
        dicts = _elements_to_dicts([elem])
        restored = _elements_from_dicts(dicts)
        assert len(restored) == 1
        assert restored[0].id == 0
        assert restored[0].bbox == (10, 20, 30, 40)
        assert restored[0].content == "hello"

    def test_empty(self):
        assert _elements_to_dicts([]) == []
        assert _elements_from_dicts([]) == []


class TestGlance:
    @patch("xclaw.core.context.glance._crop_and_parse")
    def test_keeps_unchanged_cache(self, mock_crop):
        """Elements outside change regions should be kept from cache."""
        cached = _elem(0, bbox=(0, 0, 50, 50), content="cached")
        change_regions = [(800, 800, 900, 900)]

        new_elem = _elem(1, bbox=(810, 810, 890, 890), content="new")
        mock_crop.return_value = [new_elem]

        state = ContextState(
            cached_elements=[_elem_to_dict(cached)],
            cached_resolution=(1920, 1080),
            last_screenshot_path="prev.png",
        )

        result = glance("current.png", change_regions, state)
        assert isinstance(result, GlanceResult)
        assert result.merged_from_cache >= 1
        assert result.newly_parsed >= 1
        contents = {e.content for e in result.pipeline_result.elements}
        assert "cached" in contents
        assert "new" in contents

    @patch("xclaw.core.context.glance._crop_and_parse")
    def test_discards_overlapping_cache(self, mock_crop):
        """Cached elements overlapping with change regions should be discarded."""
        cached = _elem(0, bbox=(100, 100, 200, 200), content="stale")
        change_regions = [(90, 90, 210, 210)]

        new_elem = _elem(1, bbox=(100, 100, 200, 200), content="fresh")
        mock_crop.return_value = [new_elem]

        state = ContextState(
            cached_elements=[_elem_to_dict(cached)],
            cached_resolution=(1920, 1080),
        )

        result = glance("current.png", change_regions, state)
        assert result.merged_from_cache == 0
        contents = {e.content for e in result.pipeline_result.elements}
        assert "stale" not in contents
        assert "fresh" in contents

    @patch("xclaw.core.context.glance.run_pipeline")
    def test_large_change_falls_back_to_full_pipeline(self, mock_pipeline):
        """If change area > 60% of screen, fall back to full pipeline."""
        from xclaw.core.pipeline import PipelineResult
        mock_result = PipelineResult(
            elements=[_elem(0)],
            resolution=(100, 100),
            image_path="current.png",
        )
        mock_pipeline.return_value = mock_result

        state = ContextState(cached_resolution=(100, 100))
        change_regions = [(0, 0, 90, 90)]  # 8100 / 10000 = 81%

        result = glance("current.png", change_regions, state)
        mock_pipeline.assert_called_once_with("current.png")
        assert result.merged_from_cache == 0
        assert result.newly_parsed == 1

    @patch("xclaw.core.context.glance._crop_and_parse")
    def test_empty_change_regions(self, mock_crop):
        """No change regions → only cache elements survive."""
        cached = _elem(0, bbox=(10, 10, 50, 50), content="cached")
        mock_crop.return_value = []

        state = ContextState(
            cached_elements=[_elem_to_dict(cached)],
            cached_resolution=(1920, 1080),
        )

        result = glance("current.png", [], state)
        mock_crop.assert_not_called()
        assert result.merged_from_cache == 1
        assert result.newly_parsed == 0

    @patch("xclaw.core.context.glance._crop_and_parse")
    def test_pipeline_result_has_l2(self, mock_crop):
        """Result should have L2 fields populated."""
        mock_crop.return_value = [
            _elem(0, bbox=(100, 100, 200, 200), content="item")
        ]

        state = ContextState(
            cached_elements=[],
            cached_resolution=(1920, 1080),
        )

        result = glance("current.png", [(90, 90, 210, 210)], state)
        pr = result.pipeline_result
        assert pr.columns is not None
        assert pr.reading_order is not None


class TestGlanceScroll:
    @patch("xclaw.core.context.glance._crop_and_parse")
    @patch("xclaw.core.context.scroll.shift_elements")
    @patch("xclaw.core.context.scroll.analyze_scroll")
    def test_scroll_based_glance(self, mock_analyze, mock_shift, mock_crop):
        """After scroll, glance should use ORB-based optimization."""
        from xclaw.core.context.scroll import ScrollAnalysis
        from xclaw.core.context.state import ActionRecord

        mock_analyze.return_value = ScrollAnalysis(
            offset_y=50, confidence=0.8, matched_points=20,
            new_strip=(0, 250, 1920, 300),
        )

        shifted_elem = _elem(0, bbox=(10, 50, 50, 100), content="shifted")
        mock_shift.return_value = [shifted_elem]

        new_elem = _elem(1, bbox=(10, 260, 50, 290), content="new_strip")
        mock_crop.return_value = [new_elem]

        state = ContextState(
            cached_elements=[_elem_to_dict(_elem(0, bbox=(10, 100, 50, 150), content="cached"))],
            cached_resolution=(1920, 1080),
            last_screenshot_path="prev.png",
        )
        state.action_history = [
            ActionRecord(action="scroll", params={"direction": "down", "amount": 3}, timestamp=1000.0),
        ]

        result = glance("current.png", [(0, 250, 1920, 300)], state)
        assert isinstance(result, GlanceResult)
        mock_analyze.assert_called_once()
        mock_shift.assert_called_once()
        assert result.merged_from_cache >= 1
        assert result.newly_parsed >= 1
