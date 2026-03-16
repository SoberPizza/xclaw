"""Tests for structural fingerprint pattern detection."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Row, Block
from xclaw.core.spatial.pattern_detector import (
    _row_fingerprint,
    _fingerprint_similarity,
    detect_patterns,
)


def _elem(id, type="text", x1=0, y1=0, x2=100, y2=20, content="test"):
    return RawElement(
        id=id, type=type, bbox=(x1, y1, x2, y2),
        center=((x1 + x2) // 2, (y1 + y2) // 2), content=content,
    )


class TestRowFingerprint:
    def test_basic(self):
        elems = {0: _elem(0, type="text", x1=0), 1: _elem(1, type="icon", x1=100)}
        row = Row(id=0, y_center=10, y_top=0, y_bottom=20, element_ids=[0, 1])
        fp = _row_fingerprint(row, elems, bucket_width=50)
        assert len(fp) == 2
        assert fp[0][0] == "text"
        assert fp[1][0] == "icon"

    def test_empty_row(self):
        fp = _row_fingerprint(
            Row(id=0, y_center=10, y_top=0, y_bottom=20, element_ids=[]),
            {}, bucket_width=50,
        )
        assert fp == ()


class TestFingerprintSimilarity:
    def test_identical(self):
        fp = (("text", 0), ("icon", 2))
        assert _fingerprint_similarity(fp, fp) == 1.0

    def test_completely_different(self):
        fp1 = (("text", 0),)
        fp2 = (("icon", 5),)
        assert _fingerprint_similarity(fp1, fp2) == 0.0

    def test_both_empty(self):
        assert _fingerprint_similarity((), ()) == 1.0

    def test_one_empty(self):
        assert _fingerprint_similarity((), (("text", 0),)) == 0.0


class TestDetectPatterns:
    def test_empty(self):
        assert detect_patterns([], [], []) == {}

    def test_repeating_rows_detected(self):
        # 4 identical rows → should detect pattern
        elems = [
            _elem(i, type="text", x1=0, y1=i * 30, x2=100, y2=i * 30 + 20)
            for i in range(4)
        ]
        rows = [
            Row(id=i, y_center=i * 30 + 10, y_top=i * 30, y_bottom=i * 30 + 20,
                element_ids=[i])
            for i in range(4)
        ]
        blocks = [Block(id=0, y_start=0, y_end=110, row_ids=[0, 1, 2, 3])]
        patterns = detect_patterns(blocks, rows, elems)
        assert 0 in patterns
        assert patterns[0] in ("feed", "list")

    def test_non_repeating_not_detected(self):
        # Each row has different structure
        elems = [
            _elem(0, type="text", x1=0),
            _elem(1, type="icon", x1=500),
            _elem(2, type="text", x1=1000),
        ]
        rows = [
            Row(id=0, y_center=10, y_top=0, y_bottom=20, element_ids=[0]),
            Row(id=1, y_center=50, y_top=40, y_bottom=60, element_ids=[1]),
            Row(id=2, y_center=90, y_top=80, y_bottom=100, element_ids=[2]),
        ]
        blocks = [Block(id=0, y_start=0, y_end=100, row_ids=[0, 1, 2])]
        patterns = detect_patterns(blocks, rows, elems, bucket_width=50)
        # Different x_buckets and types → should not detect
        # (0 and 1 differ, 1 and 2 differ → 0/2 similar pairs)
        assert patterns.get(0) is None
