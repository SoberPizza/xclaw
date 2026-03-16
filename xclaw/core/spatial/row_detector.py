"""Y-center greedy clustering to detect horizontal rows."""

from xclaw.config import ROW_Y_TOLERANCE
from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Row


def detect_rows(
    elements: list[RawElement],
    y_tolerance: int = ROW_Y_TOLERANCE,
) -> list[Row]:
    """Cluster elements into rows by y-center proximity.

    Algorithm:
    1. Compute y_center for each element
    2. Sort by y_center
    3. Adjacent difference > y_tolerance starts a new row
    O(n log n)
    """
    if not elements:
        return []

    sorted_elems = sorted(elements, key=lambda e: e.center[1])

    rows: list[Row] = []
    current_ids: list[int] = [sorted_elems[0].id]
    current_y_centers: list[float] = [float(sorted_elems[0].center[1])]
    current_y_top: int = sorted_elems[0].bbox[1]
    current_y_bottom: int = sorted_elems[0].bbox[3]

    for elem in sorted_elems[1:]:
        y_c = float(elem.center[1])
        if y_c - current_y_centers[-1] > y_tolerance:
            # Flush current row
            rows.append(
                Row(
                    id=len(rows),
                    y_center=sum(current_y_centers) / len(current_y_centers),
                    y_top=current_y_top,
                    y_bottom=current_y_bottom,
                    element_ids=current_ids,
                )
            )
            current_ids = [elem.id]
            current_y_centers = [y_c]
            current_y_top = elem.bbox[1]
            current_y_bottom = elem.bbox[3]
        else:
            current_ids.append(elem.id)
            current_y_centers.append(y_c)
            current_y_top = min(current_y_top, elem.bbox[1])
            current_y_bottom = max(current_y_bottom, elem.bbox[3])

    # Flush last row
    rows.append(
        Row(
            id=len(rows),
            y_center=sum(current_y_centers) / len(current_y_centers),
            y_top=current_y_top,
            y_bottom=current_y_bottom,
            element_ids=current_ids,
        )
    )

    return rows
