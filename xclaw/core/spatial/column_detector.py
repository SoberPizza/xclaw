"""X1 density clustering for column detection."""

from xclaw.config import COLUMN_MIN_GAP
from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Column


def detect_columns(
    elements: list[RawElement],
    column_min_gap: int = COLUMN_MIN_GAP,
    resolution: tuple[int, int] | None = None,
) -> list[Column]:
    """Detect vertical columns by clustering element x1 coordinates.

    Algorithm:
    1. Collect all x1 values, sort
    2. Adjacent x1 gap > column_min_gap starts a new column
    3. Each column tracks its x_start (min x1), x_end (max x2), and member ids
    4. Filter out tiny columns (< 15% width AND < 40% height) when resolution given
    """
    if not elements:
        return []

    # Sort elements by x1
    sorted_elems = sorted(elements, key=lambda e: e.bbox[0])

    columns: list[Column] = []
    current_ids: list[int] = [sorted_elems[0].id]
    current_x1s: list[int] = [sorted_elems[0].bbox[0]]
    current_x2s: list[int] = [sorted_elems[0].bbox[2]]

    for elem in sorted_elems[1:]:
        x1 = elem.bbox[0]
        if x1 - current_x1s[-1] > column_min_gap:
            # Flush current column
            columns.append(
                Column(
                    id=len(columns),
                    x_start=min(current_x1s),
                    x_end=max(current_x2s),
                    element_ids=current_ids,
                )
            )
            current_ids = [elem.id]
            current_x1s = [x1]
            current_x2s = [elem.bbox[2]]
        else:
            current_ids.append(elem.id)
            current_x1s.append(x1)
            current_x2s.append(elem.bbox[2])

    # Flush last column
    columns.append(
        Column(
            id=len(columns),
            x_start=min(current_x1s),
            x_end=max(current_x2s),
            element_ids=current_ids,
        )
    )

    # Filter tiny columns when resolution is available
    if resolution is not None:
        w, h = resolution
        min_col_w = w * 0.15
        min_col_h = h * 0.40
        filtered: list[Column] = []
        for col in columns:
            col_w = col.x_end - col.x_start
            # Compute column height from element y extents
            y_vals = []
            for elem in elements:
                if elem.id in col.element_ids:
                    y_vals.extend([elem.bbox[1], elem.bbox[3]])
            col_h = (max(y_vals) - min(y_vals)) if y_vals else 0
            # Keep column unless it's both too narrow AND too short
            if col_w >= min_col_w or col_h >= min_col_h:
                filtered.append(col)
        # Renumber
        for i, col in enumerate(filtered):
            col.id = i
        columns = filtered

    return columns
