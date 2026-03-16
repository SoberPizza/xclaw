"""Tests for L1 peek — cv2 pixel diff."""

import numpy as np
import cv2
import os
import tempfile

from xclaw.core.context.state import ContextState
from xclaw.core.context.peek import peek, _merge_nearby_contours, PeekResult


def _make_image(color: int, width: int = 200, height: int = 100) -> str:
    """Create a solid gray image and return its path."""
    img = np.full((height, width), color, dtype=np.uint8)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path


def _make_image_with_rect(
    bg: int, rect_color: int,
    rect: tuple[int, int, int, int],
    width: int = 200, height: int = 100,
) -> str:
    """Create an image with a colored rectangle."""
    img = np.full((height, width), bg, dtype=np.uint8)
    x1, y1, x2, y2 = rect
    img[y1:y2, x1:x2] = rect_color
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path


class TestMergeContours:
    def test_empty(self):
        assert _merge_nearby_contours([]) == []

    def test_single_contour(self):
        c = np.array([[[10, 10]], [[50, 10]], [[50, 50]], [[10, 50]]])
        result = _merge_nearby_contours([c])
        assert len(result) == 1
        x1, y1, x2, y2 = result[0]
        assert x1 == 10 and y1 == 10

    def test_nearby_merge(self):
        c1 = np.array([[[10, 10]], [[30, 10]], [[30, 30]], [[10, 30]]])
        c2 = np.array([[[40, 10]], [[60, 10]], [[60, 30]], [[40, 30]]])
        # Gap is 10px, merge_distance is 20 → should merge
        result = _merge_nearby_contours([c1, c2], merge_distance=20)
        assert len(result) == 1

    def test_far_apart_no_merge(self):
        c1 = np.array([[[10, 10]], [[30, 10]], [[30, 30]], [[10, 30]]])
        c2 = np.array([[[100, 10]], [[120, 10]], [[120, 30]], [[100, 30]]])
        # Gap is 70px, merge_distance is 20 → should NOT merge
        result = _merge_nearby_contours([c1, c2], merge_distance=20)
        assert len(result) == 2


class TestPeek:
    def test_no_previous_screenshot(self):
        state = ContextState()
        path = _make_image(128)
        result = peek(state, path)
        assert result.changed is True
        assert result.diff_ratio == 1.0
        assert result.suggest_level == "L3"
        os.unlink(path)

    def test_identical_images(self):
        path1 = _make_image(128)
        path2 = _make_image(128)
        state = ContextState(last_screenshot_path=path1)
        result = peek(state, path2)
        assert result.changed is False
        assert result.diff_ratio == 0.0
        assert result.suggest_level == "L1"
        os.unlink(path1)
        os.unlink(path2)

    def test_minor_change(self):
        """Small rectangle changes → minor diff → L2."""
        path1 = _make_image(128, width=400, height=200)
        # Add a small changed region (10x10 = 100 pixels out of 80000 total)
        path2 = _make_image_with_rect(128, 255, (10, 10, 40, 40), width=400, height=200)
        state = ContextState(last_screenshot_path=path1)
        result = peek(state, path2)
        assert result.changed is True
        assert result.diff_ratio < 0.15  # minor
        assert result.suggest_level == "L2"
        assert len(result.change_regions) >= 1
        os.unlink(path1)
        os.unlink(path2)

    def test_major_change(self):
        """Very different images → major diff → L3."""
        path1 = _make_image(0, width=200, height=100)
        path2 = _make_image(255, width=200, height=100)
        state = ContextState(last_screenshot_path=path1)
        result = peek(state, path2)
        assert result.changed is True
        assert result.diff_ratio > 0.15
        assert result.suggest_level == "L3"
        os.unlink(path1)
        os.unlink(path2)

    def test_detects_change_regions(self):
        """Specific changed regions should be detected."""
        path1 = _make_image(128, width=400, height=200)
        # Two separate changed areas
        img = np.full((200, 400), 128, dtype=np.uint8)
        img[10:30, 10:30] = 255  # top-left change
        img[150:180, 350:390] = 255  # bottom-right change
        fd, path2 = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        cv2.imwrite(path2, img)

        state = ContextState(last_screenshot_path=path1)
        result = peek(state, path2)
        assert result.changed is True
        assert len(result.change_regions) >= 2
        os.unlink(path1)
        os.unlink(path2)

    def test_missing_previous_file(self):
        """If previous screenshot doesn't exist, treat as full change."""
        state = ContextState(last_screenshot_path="/nonexistent/file.png")
        path = _make_image(128)
        result = peek(state, path)
        assert result.changed is True
        assert result.diff_ratio == 1.0
        os.unlink(path)

    def test_elapsed_ms(self):
        path1 = _make_image(128)
        path2 = _make_image(128)
        state = ContextState(last_screenshot_path=path1)
        result = peek(state, path2)
        assert result.elapsed_ms >= 0
        os.unlink(path1)
        os.unlink(path2)
