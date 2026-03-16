"""Universal UI component detection rules."""

from xclaw.config import CARD_MIN_ROWS, CARD_MAX_WIDTH_RATIO, SEARCHBOX_MIN_INPUT_WIDTH, MODAL_CENTER_TOLERANCE
from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Block, Row, Region
from xclaw.core.semantic.types import Component, ComponentType


def _detect_cards(
    elements_by_id: dict[int, RawElement],
    blocks: list[Block],
    rows_by_id: dict[int, Row],
    resolution: tuple[int, int],
) -> list[Component]:
    """Card: >=2 rows + has long text + width < 80% screen width."""
    w, _h = resolution
    max_card_w = w * CARD_MAX_WIDTH_RATIO
    components: list[Component] = []

    for block in blocks:
        if len(block.row_ids) < CARD_MIN_ROWS:
            continue

        # Gather all element ids in this block
        block_elem_ids: list[int] = []
        for rid in block.row_ids:
            row = rows_by_id.get(rid)
            if row:
                block_elem_ids.extend(row.element_ids)

        # Check width and text content
        xs = []
        has_long_text = False
        for eid in block_elem_ids:
            elem = elements_by_id.get(eid)
            if elem is None:
                continue
            xs.extend([elem.bbox[0], elem.bbox[2]])
            if elem.type == "text" and len(elem.content) > 10:
                has_long_text = True

        if not xs:
            continue
        block_w = max(xs) - min(xs)
        if block_w < max_card_w and has_long_text:
            components.append(
                Component(
                    id=0,  # renumbered later
                    type=ComponentType.CARD,
                    bbox=(min(xs), block.y_start, max(xs), block.y_end),
                    element_ids=block_elem_ids,
                )
            )

    return components


def _detect_action_rows(
    elements_by_id: dict[int, RawElement],
    rows: list[Row],
) -> list[Component]:
    """ActionRow: single row with >=3 icons and short content, icon-dominant."""
    components: list[Component] = []

    for row in rows:
        icon_count = 0
        non_icon_count = 0
        all_short = True
        xs = []
        for eid in row.element_ids:
            elem = elements_by_id.get(eid)
            if elem is None:
                continue
            xs.extend([elem.bbox[0], elem.bbox[2]])
            if elem.type == "icon":
                icon_count += 1
            else:
                non_icon_count += 1
            if elem.content and len(elem.content) > 10:
                all_short = False

        if icon_count >= 3 and all_short and xs and non_icon_count <= icon_count:
            components.append(
                Component(
                    id=0,
                    type=ComponentType.ACTION_ROW,
                    bbox=(min(xs), row.y_top, max(xs), row.y_bottom),
                    element_ids=list(row.element_ids),
                )
            )

    return components


def _detect_navigation(
    elements_by_id: dict[int, RawElement],
    rows: list[Row],
    regions: list[Region],
    rows_by_id: dict[int, Row],
) -> list[Component]:
    """Navigation: in header/sidebar region + >=4 evenly spaced short text items."""
    nav_roles = {"header", "sidebar"}
    nav_block_ids: set[int] = set()
    for region in regions:
        if region.role in nav_roles:
            nav_block_ids.update(region.block_ids)

    # Build row→block mapping to filter rows by region
    nav_row_ids: set[int] = set()
    from xclaw.core.spatial.types import Block
    for region in regions:
        if region.role in nav_roles:
            for bid in region.block_ids:
                # We need to find the block with this id — scan rows_by_id isn't enough
                # Use a simpler approach: check if any row's elements fall within the region bbox
                pass

    # Simpler: collect all row IDs that belong to nav blocks
    # We need block info — get it from regions + rows_by_id
    # Since we don't have blocks directly, use region bbox to filter rows
    components: list[Component] = []

    for row in rows:
        # Check if row falls within a nav region bbox
        in_nav_region = False
        for region in regions:
            if region.role in nav_roles:
                _, ry1, _, ry2 = region.bbox
                if row.y_top >= ry1 and row.y_bottom <= ry2:
                    in_nav_region = True
                    break

        if not in_nav_region:
            continue

        text_elems = []
        xs = []
        for eid in row.element_ids:
            elem = elements_by_id.get(eid)
            if elem is None:
                continue
            xs.extend([elem.bbox[0], elem.bbox[2]])
            if elem.type == "text" and len(elem.content) <= 12:
                text_elems.append(elem)

        if len(text_elems) >= 4 and xs:
            components.append(
                Component(
                    id=0,
                    type=ComponentType.NAVIGATION,
                    bbox=(min(xs), row.y_top, max(xs), row.y_bottom),
                    element_ids=list(row.element_ids),
                    properties={"item_count": len(text_elems)},
                )
            )

    return components


def _detect_search_boxes(
    elements_by_id: dict[int, RawElement],
    rows: list[Row],
    min_input_width: int = SEARCHBOX_MIN_INPUT_WIDTH,
) -> list[Component]:
    """SearchBox: wide input (>250px) + nearby icon + search-related content."""
    _search_keywords = {"search", "find", "搜索", "查找", "搜"}
    components: list[Component] = []

    for row in rows:
        wide_input_elem = None
        icon_elem = None
        xs = []
        for eid in row.element_ids:
            elem = elements_by_id.get(eid)
            if elem is None:
                continue
            xs.extend([elem.bbox[0], elem.bbox[2]])
            elem_w = elem.bbox[2] - elem.bbox[0]
            if elem.type == "text" and elem_w >= min_input_width:
                wide_input_elem = elem
            if elem.type == "icon":
                icon_elem = elem

        if not (wide_input_elem and icon_elem and xs):
            continue

        # Distance check: icon center to input bbox edge < 80px
        icon_cx = (icon_elem.bbox[0] + icon_elem.bbox[2]) / 2
        icon_cy = (icon_elem.bbox[1] + icon_elem.bbox[3]) / 2
        inp = wide_input_elem.bbox
        # Distance from icon center to nearest edge of input bbox
        dx = max(inp[0] - icon_cx, 0, icon_cx - inp[2])
        dy = max(inp[1] - icon_cy, 0, icon_cy - inp[3])
        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist > 80:
            continue

        # Content check: empty or contains search keyword
        content = wide_input_elem.content.lower().strip()
        if content:
            if not any(kw in content for kw in _search_keywords):
                continue

        components.append(
            Component(
                id=0,
                type=ComponentType.SEARCH_BOX,
                bbox=(min(xs), row.y_top, max(xs), row.y_bottom),
                element_ids=list(row.element_ids),
            )
        )

    return components


def _detect_modals(
    blocks: list[Block],
    rows_by_id: dict[int, Row],
    elements_by_id: dict[int, RawElement],
    resolution: tuple[int, int],
    center_tolerance: float = MODAL_CENTER_TOLERANCE,
) -> list[Component]:
    """Modal: centered block that doesn't touch edges, constrained size."""
    w, h = resolution
    cx = w / 2
    cy = h / 2
    tol_x = w * center_tolerance
    tol_y = h * center_tolerance
    max_block_w = w * 0.50
    max_block_h = h * 0.60

    components: list[Component] = []

    for block in blocks:
        block_elem_ids: list[int] = []
        xs: list[int] = []
        for rid in block.row_ids:
            row = rows_by_id.get(rid)
            if row:
                block_elem_ids.extend(row.element_ids)
                for eid in row.element_ids:
                    elem = elements_by_id.get(eid)
                    if elem:
                        xs.extend([elem.bbox[0], elem.bbox[2]])

        if not xs:
            continue

        bx1, bx2 = min(xs), max(xs)
        by1, by2 = block.y_start, block.y_end
        block_cx = (bx1 + bx2) / 2
        block_cy = (by1 + by2) / 2
        block_w = bx2 - bx1
        block_h = by2 - by1

        # Must be centered, not touching edges, and constrained size
        if (
            abs(block_cx - cx) < tol_x
            and abs(block_cy - cy) < tol_y
            and bx1 > w * 0.1
            and bx2 < w * 0.9
            and by1 > h * 0.1
            and by2 < h * 0.9
            and block_w < max_block_w
            and block_h < max_block_h
        ):
            components.append(
                Component(
                    id=0,
                    type=ComponentType.MODAL,
                    bbox=(bx1, by1, bx2, by2),
                    element_ids=block_elem_ids,
                )
            )

    return components


def _detect_input_fields(
    elements_by_id: dict[int, RawElement],
) -> list[Component]:
    """InputField: text element with aspect ratio > 6:1, width >= 100px, short content."""
    components: list[Component] = []

    for elem in elements_by_id.values():
        if elem.type != "text":
            continue
        ew = elem.bbox[2] - elem.bbox[0]
        eh = elem.bbox[3] - elem.bbox[1]
        if eh <= 0:
            continue
        if ew < 100:
            continue
        ratio = ew / eh
        if ratio > 6 and len(elem.content) <= 15:
            components.append(
                Component(
                    id=0,
                    type=ComponentType.INPUT_FIELD,
                    bbox=elem.bbox,
                    element_ids=[elem.id],
                )
            )

    return components


def detect_components(
    elements: list[RawElement],
    blocks: list[Block],
    rows: list[Row],
    regions: list[Region],
    resolution: tuple[int, int],
) -> list[Component]:
    """Run all component detectors and merge results with sequential ids."""
    elements_by_id = {e.id: e for e in elements}
    rows_by_id = {r.id: r for r in rows}

    all_components: list[Component] = []
    all_components.extend(_detect_cards(elements_by_id, blocks, rows_by_id, resolution))
    all_components.extend(_detect_action_rows(elements_by_id, rows))
    all_components.extend(_detect_navigation(elements_by_id, rows, regions, rows_by_id))
    all_components.extend(_detect_search_boxes(elements_by_id, rows))
    all_components.extend(_detect_modals(blocks, rows_by_id, elements_by_id, resolution))
    all_components.extend(_detect_input_fields(elements_by_id))

    # Renumber
    for i, comp in enumerate(all_components):
        comp.id = i

    return all_components
