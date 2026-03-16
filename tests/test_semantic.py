"""Tests for L3 semantic component detection and context inference."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Row, Block, Column, Region
from xclaw.core.semantic.types import ComponentType
from xclaw.core.semantic.universal import detect_components
from xclaw.core.semantic.context import infer_context


def _elem(id, type="text", x1=0, y1=0, x2=100, y2=20, content="test"):
    return RawElement(
        id=id, type=type, bbox=(x1, y1, x2, y2),
        center=((x1 + x2) // 2, (y1 + y2) // 2), content=content,
    )


class TestDetectComponents:
    def test_empty(self):
        result = detect_components([], [], [], [], (1920, 1080))
        assert result == []

    def test_card_detection(self):
        # Card: >=2 rows, text > 10 chars, width < 80% screen
        elems = [
            _elem(0, "text", 100, 100, 600, 120, content="This is a card title text"),
            _elem(1, "text", 100, 130, 600, 150, content="Card description also here"),
            _elem(2, "icon", 100, 160, 130, 180, content="heart"),
        ]
        rows = [
            Row(id=0, y_center=110, y_top=100, y_bottom=120, element_ids=[0]),
            Row(id=1, y_center=140, y_top=130, y_bottom=150, element_ids=[1]),
            Row(id=2, y_center=170, y_top=160, y_bottom=180, element_ids=[2]),
        ]
        blocks = [Block(id=0, y_start=100, y_end=180, row_ids=[0, 1, 2])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        card_types = [c for c in components if c.type == ComponentType.CARD]
        assert len(card_types) >= 1

    def test_action_row_detection(self):
        # ActionRow: >=3 icons, short content, icon-dominant
        elems = [
            _elem(0, "icon", 100, 100, 130, 130, content="like"),
            _elem(1, "icon", 140, 100, 170, 130, content="share"),
            _elem(2, "icon", 180, 100, 210, 130, content="save"),
        ]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0, 1, 2])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        action_rows = [c for c in components if c.type == ComponentType.ACTION_ROW]
        assert len(action_rows) >= 1

    def test_action_row_not_icon_dominant(self):
        # 2 icons + 3 text → non-icon-dominant, should NOT match
        elems = [
            _elem(0, "icon", 100, 100, 130, 130, content="a"),
            _elem(1, "icon", 140, 100, 170, 130, content="b"),
            _elem(2, "icon", 180, 100, 210, 130, content="c"),
            _elem(3, "text", 220, 100, 300, 130, content="text1"),
            _elem(4, "text", 310, 100, 400, 130, content="text2"),
            _elem(5, "text", 410, 100, 500, 130, content="text3"),
            _elem(6, "text", 510, 100, 600, 130, content="text4"),
        ]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0, 1, 2, 3, 4, 5, 6])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        action_rows = [c for c in components if c.type == ComponentType.ACTION_ROW]
        assert len(action_rows) == 0

    def test_input_field_detection(self):
        # Input: text type, aspect ratio > 6:1, width >= 100px, content <= 15 chars
        elems = [_elem(0, "text", 100, 100, 800, 130, content="")]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        inputs = [c for c in components if c.type == ComponentType.INPUT_FIELD]
        assert len(inputs) >= 1

    def test_input_field_rejects_non_text(self):
        # icon type should not be detected as input
        elems = [_elem(0, "icon", 100, 100, 800, 130, content="")]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        inputs = [c for c in components if c.type == ComponentType.INPUT_FIELD]
        assert len(inputs) == 0

    def test_input_field_rejects_narrow(self):
        # Width < 100px should not be detected
        elems = [_elem(0, "text", 100, 100, 190, 110, content="")]
        rows = [Row(id=0, y_center=105, y_top=100, y_bottom=110, element_ids=[0])]
        blocks = [Block(id=0, y_start=100, y_end=110, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        inputs = [c for c in components if c.type == ComponentType.INPUT_FIELD]
        assert len(inputs) == 0

    def test_input_field_rejects_long_content(self):
        # Content > 15 chars should not be detected
        elems = [_elem(0, "text", 100, 100, 800, 130, content="this is definitely too long")]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        inputs = [c for c in components if c.type == ComponentType.INPUT_FIELD]
        assert len(inputs) == 0

    def test_navigation_requires_header_region(self):
        # 4 short text items in main region → should NOT be navigation
        elems = [
            _elem(0, "text", 100, 500, 200, 520, content="Home"),
            _elem(1, "text", 210, 500, 310, 520, content="About"),
            _elem(2, "text", 320, 500, 420, 520, content="Blog"),
            _elem(3, "text", 430, 500, 530, 520, content="Contact"),
        ]
        rows = [Row(id=0, y_center=510, y_top=500, y_bottom=520, element_ids=[0, 1, 2, 3])]
        blocks = [Block(id=0, y_start=500, y_end=520, row_ids=[0])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        navs = [c for c in components if c.type == ComponentType.NAVIGATION]
        assert len(navs) == 0

    def test_navigation_in_header(self):
        # 4 short text items in header region → should be navigation
        elems = [
            _elem(0, "text", 100, 10, 200, 30, content="Home"),
            _elem(1, "text", 210, 10, 310, 30, content="About"),
            _elem(2, "text", 320, 10, 420, 30, content="Blog"),
            _elem(3, "text", 430, 10, 530, 30, content="Contact"),
        ]
        rows = [Row(id=0, y_center=20, y_top=10, y_bottom=30, element_ids=[0, 1, 2, 3])]
        blocks = [Block(id=0, y_start=10, y_end=30, row_ids=[0])]
        regions = [Region(id=0, role="header", bbox=(0, 0, 1920, 50), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        navs = [c for c in components if c.type == ComponentType.NAVIGATION]
        assert len(navs) >= 1

    def test_search_box_detection(self):
        # Wide text + nearby icon + empty content
        elems = [
            _elem(0, "icon", 100, 100, 130, 130, content="magnify"),
            _elem(1, "text", 135, 100, 500, 130, content=""),
        ]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0, 1])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="header", bbox=(0, 0, 1920, 200), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        search = [c for c in components if c.type == ComponentType.SEARCH_BOX]
        assert len(search) >= 1

    def test_search_box_rejects_non_search_content(self):
        # Wide text + icon but content is not search-related
        elems = [
            _elem(0, "icon", 100, 100, 130, 130, content="magnify"),
            _elem(1, "text", 135, 100, 500, 130, content="John Smith"),
        ]
        rows = [Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0, 1])]
        blocks = [Block(id=0, y_start=100, y_end=130, row_ids=[0])]
        regions = [Region(id=0, role="header", bbox=(0, 0, 1920, 200), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        search = [c for c in components if c.type == ComponentType.SEARCH_BOX]
        assert len(search) == 0

    def test_sequential_ids(self):
        # 3 icons (action row) + wide empty text input
        elems = [
            _elem(0, "icon", 100, 100, 130, 130, content="a"),
            _elem(1, "icon", 140, 100, 170, 130, content="b"),
            _elem(2, "icon", 180, 100, 210, 130, content="c"),
            _elem(3, "text", 200, 200, 900, 230, content=""),
        ]
        rows = [
            Row(id=0, y_center=115, y_top=100, y_bottom=130, element_ids=[0, 1, 2]),
            Row(id=1, y_center=215, y_top=200, y_bottom=230, element_ids=[3]),
        ]
        blocks = [Block(id=0, y_start=100, y_end=230, row_ids=[0, 1])]
        regions = [Region(id=0, role="main", bbox=(0, 0, 1920, 1080), block_ids=[0])]

        components = detect_components(elems, blocks, rows, regions, (1920, 1080))
        for i, comp in enumerate(components):
            assert comp.id == i


class TestInferContext:
    def test_scroll_top(self):
        elems = [_elem(0, y1=5, y2=500)]
        ctx = infer_context(elems, [], [], (1920, 1080))
        assert ctx.scroll_position == "top"

    def test_scroll_bottom(self):
        elems = [_elem(0, y1=500, y2=1078)]
        ctx = infer_context(elems, [], [], (1920, 1080))
        assert ctx.scroll_position == "bottom"

    def test_loading_few_elements(self):
        elems = [_elem(0), _elem(1)]
        ctx = infer_context(elems, [], [], (1920, 1080))
        assert ctx.loading is True

    def test_loading_text(self):
        elems = [_elem(i, content="Loading...") for i in range(10)]
        ctx = infer_context(elems, [], [], (1920, 1080))
        assert ctx.loading is True

    def test_not_loading(self):
        elems = [_elem(i, content=f"item {i}") for i in range(20)]
        ctx = infer_context(elems, [], [], (1920, 1080))
        assert ctx.loading is False

    def test_empty_elements(self):
        ctx = infer_context([], [], [], (1920, 1080))
        assert ctx.scroll_position == "unknown"
