"""Tests for Otsu-based block segmentation."""

from xclaw.core.spatial.types import Row
from xclaw.core.spatial.block_segmenter import _otsu_threshold, segment_blocks


class TestOtsuThreshold:
    def test_empty(self):
        assert _otsu_threshold([]) == 0.0

    def test_single_value(self):
        t = _otsu_threshold([5.0])
        assert t > 5.0  # threshold above the single value

    def test_bimodal(self):
        # Two clear groups: small gaps (2,3,4) and large gaps (20,25,30)
        values = [2.0, 3.0, 4.0, 20.0, 25.0, 30.0]
        t = _otsu_threshold(values)
        assert 4.0 < t < 20.0, f"Expected threshold between 4 and 20, got {t}"

    def test_uniform(self):
        values = [10.0, 10.0, 10.0]
        t = _otsu_threshold(values)
        assert t == 10.0  # all same, threshold at boundary


class TestSegmentBlocks:
    def test_empty(self):
        assert segment_blocks([], (1920, 1080)) == []

    def test_single_row(self):
        rows = [Row(id=0, y_center=100, y_top=90, y_bottom=110, element_ids=[0])]
        blocks = segment_blocks(rows, (1920, 1080))
        assert len(blocks) == 1
        assert blocks[0].row_ids == [0]

    def test_close_rows_same_block(self):
        rows = [
            Row(id=0, y_center=100, y_top=90, y_bottom=110, element_ids=[0]),
            Row(id=1, y_center=120, y_top=115, y_bottom=130, element_ids=[1]),
        ]
        blocks = segment_blocks(rows, (1920, 1080))
        # Only 1 gap, so 1 block
        assert len(blocks) == 1
        assert blocks[0].row_ids == [0, 1]

    def test_large_gap_splits_blocks(self):
        rows = [
            Row(id=0, y_center=50, y_top=40, y_bottom=60, element_ids=[0]),
            Row(id=1, y_center=70, y_top=62, y_bottom=80, element_ids=[1]),
            Row(id=2, y_center=90, y_top=82, y_bottom=100, element_ids=[2]),
            # Big gap
            Row(id=3, y_center=300, y_top=290, y_bottom=310, element_ids=[3]),
            Row(id=4, y_center=320, y_top=312, y_bottom=330, element_ids=[4]),
        ]
        blocks = segment_blocks(rows, (1920, 1080))
        assert len(blocks) == 2
        assert blocks[0].row_ids == [0, 1, 2]
        assert blocks[1].row_ids == [3, 4]

    def test_sequential_ids(self):
        rows = [
            Row(id=0, y_center=50, y_top=40, y_bottom=60, element_ids=[0]),
            Row(id=1, y_center=200, y_top=190, y_bottom=210, element_ids=[1]),
            Row(id=2, y_center=400, y_top=390, y_bottom=410, element_ids=[2]),
        ]
        blocks = segment_blocks(rows, (1920, 1080))
        assert all(b.id == i for i, b in enumerate(blocks))
