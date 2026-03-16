"""Structural fingerprint detection for feed/list patterns."""

from xclaw.config import PATTERN_BUCKET_WIDTH, PATTERN_SIMILARITY_THRESHOLD
from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Row, Block


def _row_fingerprint(
    row: Row,
    elements_by_id: dict[int, RawElement],
    bucket_width: int,
) -> tuple[tuple[str, int], ...]:
    """Generate a structural fingerprint for a row.

    Each element contributes (type, x_bucket) to the fingerprint.
    """
    parts: list[tuple[str, int]] = []
    for eid in sorted(row.element_ids):
        elem = elements_by_id.get(eid)
        if elem is None:
            continue
        x_bucket = elem.bbox[0] // bucket_width
        parts.append((elem.type, x_bucket))
    return tuple(parts)


def _fingerprint_similarity(
    fp1: tuple[tuple[str, int], ...],
    fp2: tuple[tuple[str, int], ...],
) -> float:
    """Jaccard-like similarity between two fingerprints."""
    if not fp1 and not fp2:
        return 1.0
    if not fp1 or not fp2:
        return 0.0

    set1 = set(fp1)
    set2 = set(fp2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 1.0
    return intersection / union


def detect_patterns(
    blocks: list[Block],
    rows: list[Row],
    elements: list[RawElement],
    bucket_width: int = PATTERN_BUCKET_WIDTH,
    similarity_threshold: float = PATTERN_SIMILARITY_THRESHOLD,
) -> dict[int, str]:
    """Detect repeating structural patterns within blocks.

    Returns:
        Mapping of block_id → pattern_type ("feed" | "list") for blocks
        that exhibit repeating row structure.
    """
    if not blocks or not rows or not elements:
        return {}

    elements_by_id = {e.id: e for e in elements}
    rows_by_id = {r.id: r for r in rows}

    patterns: dict[int, str] = {}

    for block in blocks:
        block_rows = [rows_by_id[rid] for rid in block.row_ids if rid in rows_by_id]
        if len(block_rows) < 2:
            continue

        # Generate fingerprints for each row in this block
        fingerprints = [
            _row_fingerprint(row, elements_by_id, bucket_width) for row in block_rows
        ]

        # Count similar adjacent row pairs
        similar_count = 0
        for i in range(len(fingerprints) - 1):
            sim = _fingerprint_similarity(fingerprints[i], fingerprints[i + 1])
            if sim >= similarity_threshold:
                similar_count += 1

        # If >60% of adjacent pairs are similar, mark as repeating pattern
        pair_count = len(fingerprints) - 1
        if pair_count > 0 and similar_count / pair_count > 0.6:
            # feed = multi-element rows, list = single-element rows
            avg_elems = sum(len(fp) for fp in fingerprints) / len(fingerprints)
            patterns[block.id] = "feed" if avg_elems > 1 else "list"

    return patterns
