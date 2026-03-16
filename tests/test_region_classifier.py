"""Tests for position-rule region classification."""

from xclaw.core.spatial.types import Block, Column, Region
from xclaw.core.spatial.region_classifier import classify_regions


class TestClassifyRegions:
    def test_empty(self):
        assert classify_regions([], [], (1920, 1080)) == []

    def test_header_detection(self):
        blocks = [Block(id=0, y_start=10, y_end=60, row_ids=[0])]
        cols = [Column(id=0, x_start=0, x_end=1900, element_ids=[0])]
        regions = classify_regions(blocks, cols, (1920, 1080))
        assert len(regions) == 1
        assert regions[0].role == "header"

    def test_footer_detection(self):
        blocks = [Block(id=0, y_start=1000, y_end=1075, row_ids=[0])]
        cols = [Column(id=0, x_start=0, x_end=1900, element_ids=[0])]
        regions = classify_regions(blocks, cols, (1920, 1080))
        assert len(regions) == 1
        assert regions[0].role == "footer"

    def test_main_content(self):
        blocks = [Block(id=0, y_start=200, y_end=800, row_ids=[0, 1, 2])]
        cols = [Column(id=0, x_start=100, x_end=1800, element_ids=[0, 1, 2])]
        regions = classify_regions(blocks, cols, (1920, 1080))
        assert len(regions) == 1
        assert regions[0].role == "main"

    def test_multiple_regions(self):
        blocks = [
            Block(id=0, y_start=10, y_end=60, row_ids=[0]),
            Block(id=1, y_start=300, y_end=800, row_ids=[1, 2]),
            Block(id=2, y_start=1000, y_end=1075, row_ids=[3]),
        ]
        cols = [Column(id=0, x_start=0, x_end=1900, element_ids=[0, 1, 2, 3])]
        regions = classify_regions(blocks, cols, (1920, 1080))
        roles = [r.role for r in regions]
        assert "header" in roles
        assert "main" in roles
        assert "footer" in roles

    def test_tall_block_at_top_not_header(self):
        # Block at top but too tall (> 15% screen height) → not header
        # 15% of 1080 = 162, block height = 620 > 162
        blocks = [Block(id=0, y_start=41, y_end=661, row_ids=[0, 1, 2])]
        cols = [Column(id=0, x_start=0, x_end=1900, element_ids=[0, 1, 2])]
        regions = classify_regions(blocks, cols, (1920, 1080))
        assert len(regions) == 1
        assert regions[0].role == "main"

    def test_tall_block_at_bottom_not_footer(self):
        # Block at bottom but too tall → not footer
        blocks = [Block(id=0, y_start=800, y_end=1075, row_ids=[0, 1])]
        cols = [Column(id=0, x_start=0, x_end=1900, element_ids=[0, 1])]
        regions = classify_regions(blocks, cols, (1920, 1080))
        assert len(regions) == 1
        assert regions[0].role == "main"
