"""Tests for column-first reading order."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Column
from xclaw.core.spatial.reading_order import sort_reading_order


def _elem(id, x1, y1, x2, y2, content=""):
    return RawElement(
        id=id, type="text", bbox=(x1, y1, x2, y2),
        center=((x1 + x2) // 2, (y1 + y2) // 2),
        content=content or f"elem{id}",
    )


class TestSortReadingOrder:
    def test_empty(self):
        assert sort_reading_order([], []) == []

    def test_single_column_top_to_bottom(self):
        elems = [
            _elem(0, 10, 100, 50, 120),
            _elem(1, 10, 200, 50, 220),
            _elem(2, 10, 50, 50, 70),
        ]
        col = Column(id=0, x_start=10, x_end=50, element_ids=[0, 1, 2])
        order = sort_reading_order(elems, [col])
        assert order == [2, 0, 1]  # sorted by y_center: 60, 110, 210

    def test_two_columns_left_to_right(self):
        elems = [
            _elem(0, 10, 100, 50, 120),    # col 0, y_center=110
            _elem(1, 10, 50, 50, 70),       # col 0, y_center=60
            _elem(2, 300, 100, 350, 120),   # col 1, y_center=110
            _elem(3, 300, 50, 350, 70),     # col 1, y_center=60
        ]
        col0 = Column(id=0, x_start=10, x_end=50, element_ids=[0, 1])
        col1 = Column(id=1, x_start=300, x_end=350, element_ids=[2, 3])
        order = sort_reading_order(elems, [col0, col1])
        # col0 first (top-to-bottom): 1, 0; then col1: 3, 2
        assert order == [1, 0, 3, 2]

    def test_unassigned_elements_appended(self):
        elems = [
            _elem(0, 10, 100, 50, 120),
            _elem(1, 500, 500, 550, 520),  # not in any column
        ]
        col = Column(id=0, x_start=10, x_end=50, element_ids=[0])
        order = sort_reading_order(elems, [col])
        assert order == [0, 1]

    def test_no_columns_sorts_by_y_then_x(self):
        elems = [
            _elem(0, 300, 100, 350, 120),  # y=110, x=325
            _elem(1, 10, 100, 50, 120),    # y=110, x=30
            _elem(2, 10, 50, 50, 70),      # y=60,  x=30
        ]
        order = sort_reading_order(elems, [])
        # sorted by (y_center, x_center): elem2(60,30), elem1(110,30), elem0(110,325)
        assert order == [2, 1, 0]

    def test_all_elements_present_in_output(self):
        elems = [_elem(i, i * 100, i * 50, i * 100 + 50, i * 50 + 20) for i in range(5)]
        col = Column(id=0, x_start=0, x_end=500, element_ids=[0, 2, 4])
        order = sort_reading_order(elems, [col])
        assert set(order) == {0, 1, 2, 3, 4}
        assert len(order) == 5
