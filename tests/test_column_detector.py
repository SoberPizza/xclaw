"""Tests for x-overlap connected-component column detection."""

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
        # Three overlapping elements → one column
        elems = [_elem(0, 10, 100), _elem(1, 15, 110), _elem(2, 20, 120)]
        cols = detect_columns(elems)
        assert len(cols) == 1
        assert len(cols[0].element_ids) == 3

    def test_two_columns(self):
        # Two groups with no x-overlap
        elems = [
            _elem(0, 10, 100),
            _elem(1, 15, 110),
            _elem(2, 500, 600),
            _elem(3, 510, 610),
        ]
        cols = detect_columns(elems)
        assert len(cols) == 2
        assert set(cols[0].element_ids) == {0, 1}
        assert set(cols[1].element_ids) == {2, 3}

    def test_column_boundaries(self):
        elems = [_elem(0, 50, 150), _elem(1, 60, 200)]
        cols = detect_columns(elems)
        assert cols[0].x_start == 50
        assert cols[0].x_end == 200

    def test_three_columns(self):
        elems = [
            _elem(0, 10, 50),
            _elem(1, 300, 350),
            _elem(2, 600, 650),
        ]
        cols = detect_columns(elems)
        assert len(cols) == 3

    def test_filter_tiny_column(self):
        # A narrow + short column should be filtered when resolution given
        elems = [
            _elem(0, 10, 30, y1=0, y2=10),        # narrow, short → tiny
            _elem(1, 500, 900, y1=0, y2=500),      # wide, tall → kept
        ]
        cols = detect_columns(elems, resolution=(1920, 1080))
        assert len(cols) == 1
        assert cols[0].element_ids == [1]

    def test_keep_narrow_but_tall_column(self):
        # Narrow but tall column should be kept (sidebar-like)
        elems = [
            _elem(0, 10, 100, y1=0, y2=500),       # narrow but tall
            _elem(1, 500, 900, y1=0, y2=500),       # wide + tall
        ]
        cols = detect_columns(elems, resolution=(1920, 1080))
        assert len(cols) == 2

    def test_no_filter_without_resolution(self):
        # Without resolution, no filtering
        elems = [
            _elem(0, 10, 30, y1=0, y2=10),
            _elem(1, 500, 900, y1=0, y2=500),
        ]
        cols = detect_columns(elems)
        assert len(cols) == 2

    def test_columns_sorted_by_x_start(self):
        # Elements given in reverse x order should still produce sorted columns
        elems = [
            _elem(0, 600, 650),
            _elem(1, 10, 50),
            _elem(2, 300, 350),
        ]
        cols = detect_columns(elems)
        assert len(cols) == 3
        assert cols[0].x_start < cols[1].x_start < cols[2].x_start

    def test_overlapping_elements_merge(self):
        # Elements with >50% x-overlap should be in the same column
        elems = [
            _elem(0, 100, 200),
            _elem(1, 120, 220),  # 80/100 = 80% overlap with elem 0
        ]
        cols = detect_columns(elems)
        assert len(cols) == 1

    def test_column_ids_sequential(self):
        elems = [
            _elem(0, 10, 50),
            _elem(1, 300, 350),
            _elem(2, 600, 650),
        ]
        cols = detect_columns(elems)
        assert [c.id for c in cols] == [0, 1, 2]

    def test_merge_overlapping_x_ranges(self):
        # Two groups with heavily overlapping x-ranges should merge into one column
        elems = [
            _elem(0, 100, 300),   # group A: wide element
            _elem(1, 150, 250),   # group A: narrow, fully inside group A
            _elem(2, 200, 280),   # between A and B x-centers, overlaps A heavily
            _elem(3, 190, 310),   # overlaps A range
        ]
        cols = detect_columns(elems)
        assert len(cols) == 1

    def test_no_merge_separate_columns(self):
        # Completely non-overlapping columns should stay separate
        elems = [
            _elem(0, 10, 100),
            _elem(1, 20, 90),
            _elem(2, 500, 600),
            _elem(3, 510, 590),
        ]
        cols = detect_columns(elems)
        assert len(cols) == 2
        assert cols[0].x_end < cols[1].x_start

    def test_cascade_merge(self):
        # Three columns that overlap pairwise in a chain should cascade-merge
        # A(100-300) overlaps B(250-450), B overlaps C(400-600)
        # After merging A+B → (100-450), that overlaps C → all merge
        elems = [
            _elem(0, 100, 300),
            _elem(1, 250, 450),
            _elem(2, 400, 600),
        ]
        # These elements all have >50% pairwise overlap at element level,
        # but let's ensure even if union-find missed the chain, column merge catches it.
        cols = detect_columns(elems)
        assert len(cols) == 1
        assert cols[0].x_start == 100
        assert cols[0].x_end == 600
