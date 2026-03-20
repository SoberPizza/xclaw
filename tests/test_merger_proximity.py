"""Tests for merger proximity-based classify skip."""

from __future__ import annotations

from xclaw.core.perception.merger import fuse_results
from xclaw.core.perception.types import TextBox


def _make_text_box(bbox, text="Label"):
    return TextBox(bbox=bbox, text=text, confidence=0.95)


class TestFuseProximitySkip:
    def test_icon_near_text_skips_classify(self):
        """Icon 10px from text (< 16px threshold) should NOT need classification."""
        icons = [{"bbox": (100, 100, 130, 130), "confidence": 0.9}]
        texts = [_make_text_box((140, 100, 200, 130))]  # 10px gap

        merged, needing_classify = fuse_results(icons, texts)
        assert len(merged) == 2  # 1 text + 1 icon
        assert len(needing_classify) == 0  # skipped due to proximity

    def test_icon_far_from_text_needs_classify(self):
        """Icon 50px from text (> 16px threshold) should need classification."""
        icons = [{"bbox": (100, 100, 130, 130), "confidence": 0.9}]
        texts = [_make_text_box((200, 100, 260, 130))]  # 70px gap

        merged, needing_classify = fuse_results(icons, texts)
        assert len(merged) == 2
        assert len(needing_classify) == 1

    def test_icon_overlapping_text_skips_classify(self):
        """Icon with IoU > 0.3 text overlap should be skipped (existing behavior)."""
        icons = [{"bbox": (100, 100, 200, 200), "confidence": 0.9}]
        texts = [_make_text_box((110, 110, 190, 190))]

        merged, needing_classify = fuse_results(icons, texts)
        assert len(needing_classify) == 0

    def test_icon_no_text_at_all(self):
        """Icon with no nearby text should need classification."""
        icons = [{"bbox": (100, 100, 130, 130), "confidence": 0.9}]
        texts = []

        merged, needing_classify = fuse_results(icons, texts)
        assert len(needing_classify) == 1
