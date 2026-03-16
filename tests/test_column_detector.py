"""Tests for X1 density column detection."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.column_detector import detect_columns


def _elem(id, x1, x2, y1=0, y2=20):
    return RawElement(
        id=id, type="text", bbox=(x1, y1, x2, y2),
        center=((x1 + x2) // 2, (y1 + y2) // 2), content=f"elem{id}",
    )


class TestDetectColumns:
    def test_empty(self):
        assert detect_columns([]) == []

    def test_single_column(self):
        elems = [_elem(0, 10, 100), _elem(1, 15, 110), _elem(2, 20, 120)]
        cols = detect_columns(elems, column_min_gap=100)
        assert len(cols) == 1
        assert len(cols[0].element_ids) == 3

    def test_two_columns(self):
        elems = [
            _elem(0, 10, 100),
            _elem(1, 15, 110),
            _elem(2, 300, 400),
            _elem(3, 310, 410),
        ]
        cols = detect_columns(elems, column_min_gap=100)
        assert len(cols) == 2
        assert set(cols[0].element_ids) == {0, 1}
        assert set(cols[1].element_ids) == {2, 3}

    def test_column_boundaries(self):
        elems = [_elem(0, 50, 150), _elem(1, 60, 200)]
        cols = detect_columns(elems, column_min_gap=100)
        assert cols[0].x_start == 50
        assert cols[0].x_end == 200

    def test_three_columns(self):
        elems = [
            _elem(0, 10, 50),
            _elem(1, 300, 350),
            _elem(2, 600, 650),
        ]
        cols = detect_columns(elems, column_min_gap=100)
        assert len(cols) == 3

    def test_filter_tiny_column(self):
        # A narrow + short column should be filtered when resolution given
        elems = [
            _elem(0, 10, 100, y1=0, y2=50),       # narrow, short → tiny
            _elem(1, 500, 900, y1=0, y2=500),      # wide, tall → kept
        ]
        cols = detect_columns(elems, column_min_gap=100, resolution=(1920, 1080))
        assert len(cols) == 1
        assert cols[0].element_ids == [1]

    def test_keep_narrow_but_tall_column(self):
        # Narrow but tall column should be kept (sidebar-like)
        elems = [
            _elem(0, 10, 100, y1=0, y2=500),       # narrow but tall
            _elem(1, 500, 900, y1=0, y2=500),       # wide + tall
        ]
        cols = detect_columns(elems, column_min_gap=100, resolution=(1920, 1080))
        assert len(cols) == 2

    def test_no_filter_without_resolution(self):
        # Without resolution, no filtering
        elems = [
            _elem(0, 10, 100, y1=0, y2=50),
            _elem(1, 500, 900, y1=0, y2=500),
        ]
        cols = detect_columns(elems, column_min_gap=100)
        assert len(cols) == 2
