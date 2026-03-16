"""IoU-based element deduplication and merging."""

from xclaw.config import MERGER_IOU_THRESHOLD
from xclaw.core.perception.types import RawElement


def box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Compute IoU between two (x1, y1, x2, y2) bboxes."""
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter

    if union <= 0:
        return 0.0
    return inter / union


def merge_elements(
    elements: list[RawElement],
    iou_threshold: float = MERGER_IOU_THRESHOLD,
) -> list[RawElement]:
    """Deduplicate overlapping elements using IoU.

    Algorithm:
    1. Sort by bbox area descending (larger elements first)
    2. For each element, check IoU with already-kept elements
    3. IoU > threshold:
       - Same type → discard (duplicate)
       - Different type → merge content into the kept element
    4. Renumber ids sequentially
    """
    if not elements:
        return []

    def _area(e: RawElement) -> int:
        return (e.bbox[2] - e.bbox[0]) * (e.bbox[3] - e.bbox[1])

    sorted_elems = sorted(elements, key=_area, reverse=True)

    kept: list[RawElement] = []
    # Track merged content additions (index in kept → extra content)
    extra_content: dict[int, list[str]] = {}

    for elem in sorted_elems:
        merged = False
        for ki, kept_elem in enumerate(kept):
            iou = box_iou(elem.bbox, kept_elem.bbox)
            if iou > iou_threshold:
                if elem.type == kept_elem.type:
                    # Same type, high overlap → duplicate, discard
                    merged = True
                    break
                else:
                    # Different type, high overlap → merge content
                    if elem.content:
                        extra_content.setdefault(ki, []).append(elem.content)
                    merged = True
                    break
        if not merged:
            kept.append(elem)

    # Rebuild with merged content and sequential ids
    result: list[RawElement] = []
    for i, elem in enumerate(kept):
        content = elem.content
        if i in extra_content:
            content = content + " " + " ".join(extra_content[i]) if content else " ".join(extra_content[i])
        result.append(
            RawElement(
                id=i,
                type=elem.type,
                bbox=elem.bbox,
                center=elem.center,
                content=content,
                confidence=elem.confidence,
                source=elem.source,
            )
        )

    return result
