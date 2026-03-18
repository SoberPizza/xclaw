"""Column-first, top-to-bottom reading order."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Column


def sort_reading_order(
    elements: list[RawElement],
    columns: list[Column],
) -> list[int]:
    """Sort elements in reading order: left-to-right by column, top-to-bottom within.

    Elements not assigned to any column are appended at the end sorted by y then x.

    Returns:
        List of element IDs in reading order.
    """
    if not elements:
        return []

    elem_by_id = {e.id: e for e in elements}

    # Collect assigned element IDs
    assigned: set[int] = set()
    # Columns are already sorted by x_start from detect_columns
    ordered: list[int] = []

    for col in columns:
        col_elems = [
            (elem_by_id[eid].center[1], eid)
            for eid in col.element_ids
            if eid in elem_by_id
        ]
        col_elems.sort()  # sort by y_center
        for _, eid in col_elems:
            ordered.append(eid)
            assigned.add(eid)

    # Append unassigned elements
    unassigned = [
        (e.center[1], e.center[0], e.id)
        for e in elements
        if e.id not in assigned
    ]
    unassigned.sort()
    for _, _, eid in unassigned:
        ordered.append(eid)

    return ordered
