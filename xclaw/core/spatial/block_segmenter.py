"""Otsu-based adaptive block segmentation."""

from xclaw.core.spatial.types import Row, Block


def _otsu_threshold(values: list[float]) -> float:
    """Compute optimal binary threshold using Otsu's method.

    Maximizes inter-class variance on a 1D array of values.
    Pure Python, ~25 lines, no numpy needed.
    """
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0] + 1.0

    sorted_v = sorted(values)
    n = len(sorted_v)
    total_sum = sum(sorted_v)
    total_mean = total_sum / n

    best_threshold = sorted_v[0]
    best_variance = 0.0

    sum_left = 0.0
    count_left = 0

    for i in range(n - 1):
        count_left += 1
        count_right = n - count_left
        sum_left += sorted_v[i]
        sum_right = total_sum - sum_left

        mean_left = sum_left / count_left
        mean_right = sum_right / count_right

        variance = count_left * count_right * (mean_left - mean_right) ** 2

        if variance > best_variance:
            best_variance = variance
            # Threshold between current and next value
            best_threshold = (sorted_v[i] + sorted_v[i + 1]) / 2.0

    return best_threshold


def segment_blocks(
    rows: list[Row],
    resolution: tuple[int, int],
) -> list[Block]:
    """Segment rows into blocks using Otsu adaptive gap threshold.

    Algorithm:
    1. Compute gaps between consecutive rows
    2. Apply Otsu to find optimal gap threshold
    3. Split at gaps > threshold
    """
    if not rows:
        return []

    if len(rows) == 1:
        return [
            Block(
                id=0,
                y_start=rows[0].y_top,
                y_end=rows[0].y_bottom,
                row_ids=[rows[0].id],
                gap_above=0.0,
            )
        ]

    # Compute inter-row gaps
    gaps: list[float] = []
    for i in range(len(rows) - 1):
        gap = max(0.0, float(rows[i + 1].y_top - rows[i].y_bottom))
        gaps.append(gap)

    threshold = _otsu_threshold(gaps)

    # Segment into blocks
    blocks: list[Block] = []
    current_row_ids: list[int] = [rows[0].id]
    current_y_start: int = rows[0].y_top
    current_y_end: int = rows[0].y_bottom
    current_gap_above: float = 0.0

    for i, gap in enumerate(gaps):
        next_row = rows[i + 1]
        if gap > threshold:
            # Flush current block
            blocks.append(
                Block(
                    id=len(blocks),
                    y_start=current_y_start,
                    y_end=current_y_end,
                    row_ids=current_row_ids,
                    gap_above=current_gap_above,
                )
            )
            current_row_ids = [next_row.id]
            current_y_start = next_row.y_top
            current_y_end = next_row.y_bottom
            current_gap_above = gap
        else:
            current_row_ids.append(next_row.id)
            current_y_end = max(current_y_end, next_row.y_bottom)

    # Flush last block
    blocks.append(
        Block(
            id=len(blocks),
            y_start=current_y_start,
            y_end=current_y_end,
            row_ids=current_row_ids,
            gap_above=current_gap_above,
        )
    )

    return blocks
