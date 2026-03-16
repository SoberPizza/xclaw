"""Tests for Y-center row detection."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.row_detector import detect_rows


def _elem(id, y1, y2, x1=0, x2=100):
    cy = (y1 + y2) // 2
    return RawElement(
        id=id, type="text", bbox=(x1, y1, x2, y2),
        center=((x1 + x2) // 2, cy), content=f"elem{id}",
    )


class TestDetectRows:
    def test_empty(self):
        assert detect_rows([]) == []

    def test_single_element(self):
        rows = detect_rows([_elem(0, 10, 20)])
        assert len(rows) == 1
        assert rows[0].element_ids == [0]

    def test_same_row(self):
        elems = [_elem(0, 10, 20), _elem(1, 12, 22)]
        rows = detect_rows(elems, y_tolerance=8)
        assert len(rows) == 1
        assert set(rows[0].element_ids) == {0, 1}

    def test_two_rows(self):
        elems = [_elem(0, 10, 20), _elem(1, 50, 60)]
        rows = detect_rows(elems, y_tolerance=8)
        assert len(rows) == 2
        assert rows[0].element_ids == [0]
        assert rows[1].element_ids == [1]

    def test_row_boundaries(self):
        elems = [_elem(0, 10, 30), _elem(1, 12, 25)]
        rows = detect_rows(elems, y_tolerance=8)
        assert rows[0].y_top == 10
        assert rows[0].y_bottom == 30

    def test_sequential_ids(self):
        elems = [_elem(0, 10, 20), _elem(1, 50, 60), _elem(2, 100, 110)]
        rows = detect_rows(elems)
        assert [r.id for r in rows] == [0, 1, 2]
