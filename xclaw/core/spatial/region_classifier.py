"""Position-rule-based region classification."""

from xclaw.config import (
    REGION_HEADER_THRESHOLD,
    REGION_FOOTER_THRESHOLD,
    REGION_SIDEBAR_MAX_WIDTH,
    REGION_MIN_SPAN,
)
from xclaw.core.spatial.types import Block, Column, Region


def classify_regions(
    blocks: list[Block],
    columns: list[Column],
    resolution: tuple[int, int],
) -> list[Region]:
    """Classify blocks into regions based on position rules.

    Rules:
    - header: y_start < 8%H and width > 70%W
    - footer: y_end > 92%H and width > 70%W
    - sidebar: narrow (< 30%W), tall (> 50%H), edge-aligned
    - main: everything else
    """
    if not blocks:
        return []

    w, h = resolution
    header_y = h * REGION_HEADER_THRESHOLD
    footer_y = h * REGION_FOOTER_THRESHOLD
    min_span_w = w * REGION_MIN_SPAN
    sidebar_max_w = w * REGION_SIDEBAR_MAX_WIDTH

    # Build a map from element coverage per block
    # We need to estimate block width from columns
    # For simplicity, use column info to get x extents per block
    block_col_map: dict[int, tuple[int, int]] = {}
    for block in blocks:
        row_id_set = set(block.row_ids)
        # Find columns that contain elements from this block's rows
        # We'll approximate: each block spans from min_x to max_x of its columns
        bx1, bx2 = w, 0
        for col in columns:
            # Check overlap by seeing if any column element belongs to the block's rows
            # Since we don't have direct row→element mapping here, use block y-range
            bx1 = min(bx1, col.x_start)
            bx2 = max(bx2, col.x_end)
        if bx2 <= bx1:
            bx1, bx2 = 0, w
        block_col_map[block.id] = (bx1, bx2)

    regions: list[Region] = []

    for block in blocks:
        bx1, bx2 = block_col_map.get(block.id, (0, w))
        block_w = bx2 - bx1
        block_h = block.y_end - block.y_start

        if block.y_start < header_y and block_w >= min_span_w and block_h < h * 0.15:
            role = "header"
        elif block.y_end > footer_y and block_w >= min_span_w and block_h < h * 0.15:
            role = "footer"
        elif (
            block_w < sidebar_max_w
            and block_h > h * 0.5
            and (bx1 < w * 0.1 or bx2 > w * 0.9)
        ):
            role = "sidebar"
        else:
            role = "main"

        regions.append(
            Region(
                id=len(regions),
                role=role,
                bbox=(bx1, block.y_start, bx2, block.y_end),
                block_ids=[block.id],
            )
        )

    return regions
