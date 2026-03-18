"""X-overlap connected-component column detection."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Column


def _find(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(parent: list[int], rank: list[int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra == rb:
        return
    if rank[ra] < rank[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    if rank[ra] == rank[rb]:
        rank[ra] += 1


def _x_overlap_ratio(ax1: int, ax2: int, bx1: int, bx2: int) -> float:
    """Fraction of overlap relative to the narrower element's width."""
    overlap = max(0, min(ax2, bx2) - max(ax1, bx1))
    min_width = min(ax2 - ax1, bx2 - bx1)
    return overlap / min_width if min_width > 0 else 0.0


def _merge_overlapping_columns(columns: list[Column], merge_ratio: float = 0.20) -> list[Column]:
    """Greedily merge columns whose x-ranges overlap by more than *merge_ratio*.

    Overlap is measured as ``overlap / min(width_a, width_b)``.  After each
    merge the absorbing column's x-range widens, which may cascade into
    further merges, so we loop until stable.
    """
    changed = True
    while changed:
        changed = False
        cols = sorted(columns, key=lambda c: c.x_start)
        new_cols: list[Column] = []
        used: set[int] = set()
        for i, a in enumerate(cols):
            if i in used:
                continue
            for j in range(i + 1, len(cols)):
                if j in used:
                    continue
                b = cols[j]
                overlap = max(0, min(a.x_end, b.x_end) - max(a.x_start, b.x_start))
                min_w = min(a.x_end - a.x_start, b.x_end - b.x_start)
                if min_w > 0 and overlap / min_w > merge_ratio:
                    a = Column(
                        id=0,
                        x_start=min(a.x_start, b.x_start),
                        x_end=max(a.x_end, b.x_end),
                        element_ids=a.element_ids + b.element_ids,
                    )
                    used.add(j)
                    changed = True
            new_cols.append(a)
            used.add(i)
        columns = new_cols
    return columns


def detect_columns(
    elements: list[RawElement],
    resolution: tuple[int, int] | None = None,
    overlap_threshold: float = 0.50,
) -> list[Column]:
    """Detect vertical columns via x-extent overlap connected components.

    Algorithm:
    1. Sort elements by x-center
    2. For adjacent pairs, if x-ranges overlap >50%, union-find merge
    3. Each connected component = one column
    4. Merge columns whose x-ranges heavily overlap (column-level pass)
    5. Filter tiny columns (< 10% screen width AND < 10% screen height)
    6. Return columns sorted by x_start
    """
    if not elements:
        return []

    n = len(elements)
    sorted_elems = sorted(elements, key=lambda e: e.center[0])

    parent = list(range(n))
    rank = [0] * n

    for i in range(n - 1):
        a = sorted_elems[i]
        b = sorted_elems[i + 1]
        ratio = _x_overlap_ratio(a.bbox[0], a.bbox[2], b.bbox[0], b.bbox[2])
        if ratio > overlap_threshold:
            _union(parent, rank, i, i + 1)

    # Group elements by component root
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = _find(parent, i)
        groups.setdefault(root, []).append(i)

    # Build columns
    columns: list[Column] = []
    for indices in groups.values():
        eids = [sorted_elems[i].id for i in indices]
        x_starts = [sorted_elems[i].bbox[0] for i in indices]
        x_ends = [sorted_elems[i].bbox[2] for i in indices]
        columns.append(Column(
            id=0,
            x_start=min(x_starts),
            x_end=max(x_ends),
            element_ids=eids,
        ))

    # Column-level merge: collapse columns with heavily overlapping x-ranges
    columns = _merge_overlapping_columns(columns)

    # Filter tiny columns if resolution is known
    if resolution is not None:
        w, h = resolution
        min_w = w * 0.10
        min_h = h * 0.10
        elem_by_id = {e.id: e for e in elements}
        filtered: list[Column] = []
        for col in columns:
            col_w = col.x_end - col.x_start
            y_vals = []
            for eid in col.element_ids:
                e = elem_by_id.get(eid)
                if e:
                    y_vals.extend([e.bbox[1], e.bbox[3]])
            col_h = (max(y_vals) - min(y_vals)) if y_vals else 0
            if col_w >= min_w or col_h >= min_h:
                filtered.append(col)
        columns = filtered

    # Sort by x_start, renumber
    columns.sort(key=lambda c: c.x_start)
    for i, col in enumerate(columns):
        col.id = i

    return columns
