"""Tests for scroll offset tracking."""

import os
import tempfile

import cv2
import numpy as np

from xclaw.core.perception.types import RawElement
from xclaw.core.context.scroll import analyze_scroll, shift_elements, ScrollAnalysis


def _elem(id, bbox=(0, 0, 10, 10), content="test"):
    return RawElement(
        id=id, type="text", bbox=bbox,
        center=((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2),
        content=content,
    )


def _make_scroll_images(width=400, height=300, offset=50):
    """Create two images simulating a downward scroll.

    Generates a pattern image and shifts it to simulate scrolling.
    Returns (prev_path, curr_path).
    """
    # Create a pattern with distinct features (random blocks)
    rng = np.random.RandomState(42)
    # Make a tall canvas, then crop two overlapping windows
    tall_h = height + abs(offset) + 100
    canvas = np.zeros((tall_h, width), dtype=np.uint8)

    # Add random rectangles for ORB features
    for _ in range(50):
        x1 = rng.randint(0, width - 30)
        y1 = rng.randint(0, tall_h - 30)
        x2 = x1 + rng.randint(10, 30)
        y2 = y1 + rng.randint(10, 30)
        color = rng.randint(100, 255)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), int(color), -1)

    # Crop two windows
    prev = canvas[0:height, :]
    curr = canvas[offset:offset + height, :]

    fd1, prev_path = tempfile.mkstemp(suffix=".png")
    os.close(fd1)
    cv2.imwrite(prev_path, prev)

    fd2, curr_path = tempfile.mkstemp(suffix=".png")
    os.close(fd2)
    cv2.imwrite(curr_path, curr)

    return prev_path, curr_path


class TestAnalyzeScroll:
    def test_identical_images(self):
        """No scroll → offset should be 0."""
        rng = np.random.RandomState(42)
        img = np.zeros((300, 400), dtype=np.uint8)
        for _ in range(30):
            x1, y1 = rng.randint(0, 370), rng.randint(0, 270)
            cv2.rectangle(img, (x1, y1), (x1 + 20, y1 + 20), int(rng.randint(100, 255)), -1)

        fd1, p1 = tempfile.mkstemp(suffix=".png")
        os.close(fd1)
        cv2.imwrite(p1, img)
        fd2, p2 = tempfile.mkstemp(suffix=".png")
        os.close(fd2)
        cv2.imwrite(p2, img)

        result = analyze_scroll(p2, p1, (400, 300))
        assert abs(result.offset_y) <= 3  # near zero
        os.unlink(p1)
        os.unlink(p2)

    def test_scroll_down(self):
        """Scrolling down → positive offset."""
        prev_path, curr_path = _make_scroll_images(offset=50)
        result = analyze_scroll(curr_path, prev_path, (400, 300))
        # Should detect approximately 50px scroll
        assert result.offset_y > 20  # allow some tolerance for ORB
        assert result.matched_points > 0
        if result.new_strip is not None:
            assert result.new_strip[1] < result.new_strip[3]  # valid bbox
        os.unlink(prev_path)
        os.unlink(curr_path)

    def test_missing_image(self):
        """Missing file → zero offset with 0 confidence."""
        result = analyze_scroll("/nonexistent.png", "/also_nonexistent.png", (400, 300))
        assert result.offset_y == 0
        assert result.confidence == 0.0

    def test_new_strip_scroll_down(self):
        """New strip should be at the bottom when scrolling down."""
        prev_path, curr_path = _make_scroll_images(offset=80)
        result = analyze_scroll(curr_path, prev_path, (400, 300))
        if result.new_strip is not None and result.offset_y > 10:
            # New content appears at the bottom
            assert result.new_strip[1] >= 200  # bottom half
        os.unlink(prev_path)
        os.unlink(curr_path)


class TestShiftElements:
    def test_scroll_down_shifts_up(self):
        """Scrolling down = elements move up."""
        elems = [
            _elem(0, bbox=(10, 100, 50, 150)),
            _elem(1, bbox=(10, 200, 50, 250)),
        ]
        shifted = shift_elements(elems, offset_y=50, resolution=(400, 300))
        assert len(shifted) == 2
        # y coordinates should decrease by 50
        assert shifted[0].bbox[1] == 50
        assert shifted[1].bbox[1] == 150

    def test_removes_out_of_viewport(self):
        """Elements scrolled out of viewport should be removed."""
        elems = [
            _elem(0, bbox=(10, 10, 50, 40)),  # will scroll out (y becomes -40 to -10)
            _elem(1, bbox=(10, 200, 50, 250)),  # stays
        ]
        shifted = shift_elements(elems, offset_y=60, resolution=(400, 300))
        assert len(shifted) == 1
        assert shifted[0].id == 1

    def test_scroll_up_shifts_down(self):
        """Scrolling up (negative offset) = elements move down."""
        elems = [_elem(0, bbox=(10, 50, 50, 100))]
        shifted = shift_elements(elems, offset_y=-30, resolution=(400, 300))
        assert len(shifted) == 1
        assert shifted[0].bbox[1] == 80  # 50 - (-30) = 80

    def test_empty_input(self):
        assert shift_elements([], offset_y=50, resolution=(400, 300)) == []

    def test_zero_offset(self):
        elems = [_elem(0, bbox=(10, 100, 50, 150))]
        shifted = shift_elements(elems, offset_y=0, resolution=(400, 300))
        assert len(shifted) == 1
        assert shifted[0].bbox == (10, 100, 50, 150)
