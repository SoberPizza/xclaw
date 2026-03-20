"""IoU-based element deduplication and merging."""

import math

from xclaw.config import (
    MERGER_IOU_THRESHOLD,
    MERGER_PROXIMITY_THRESHOLD,
    MERGER_SMALL_ELEMENT_CENTER_DIST,
    MERGER_SMALL_ELEMENT_SIZE,
)
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


def _is_small(bbox: tuple[int, int, int, int], threshold: int = MERGER_SMALL_ELEMENT_SIZE) -> bool:
    """True if element is smaller than *threshold* in both dimensions."""
    return (bbox[2] - bbox[0]) < threshold and (bbox[3] - bbox[1]) < threshold


def _center_distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Euclidean distance between bbox centers."""
    acx = (a[0] + a[2]) / 2
    acy = (a[1] + a[3]) / 2
    bcx = (b[0] + b[2]) / 2
    bcy = (b[1] + b[3]) / 2
    return math.hypot(acx - bcx, acy - bcy)


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
            # Adaptive overlap metric: small elements use center-distance
            if _is_small(elem.bbox) and _is_small(kept_elem.bbox):
                is_overlap = _center_distance(elem.bbox, kept_elem.bbox) < MERGER_SMALL_ELEMENT_CENTER_DIST
            else:
                is_overlap = box_iou(elem.bbox, kept_elem.bbox) > iou_threshold

            if is_overlap:
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
            extra = " ".join(extra_content[i])
            content = f"{content} {extra}".strip() if content else extra
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


def fuse_results(icon_boxes: list[dict], text_boxes) -> tuple[list[dict], list[dict]]:
    """Fuse YOLO icon detections and OCR text boxes.

    Returns:
        (merged_elements, icons_needing_classify)
        - merged_elements: all elements with type/bbox/content
        - icons_needing_classify: icon elements without text overlap or proximity
    """
    merged = []
    icons_needing_classify = []

    # Convert text_boxes to dicts
    text_dicts = []
    for tb in text_boxes:
        text_dicts.append({
            "type": "text",
            "bbox": tb.bbox if isinstance(tb.bbox, tuple) else tuple(tb.bbox),
            "content": tb.text if hasattr(tb, 'text') else tb.get("text", ""),
            "confidence": tb.confidence if hasattr(tb, 'confidence') else tb.get("confidence", 1.0),
        })

    # Add all text boxes
    for td in text_dicts:
        merged.append(td)

    # Process icon boxes: check text overlap and proximity
    for icon in icon_boxes:
        icon_bbox = icon["bbox"]
        has_text_overlap = False
        has_text_nearby = False

        for td in text_dicts:
            tb = td["bbox"]
            iou = box_iou(icon_bbox, tb)
            if iou > 0.3:
                has_text_overlap = True
                break
            # proximity check (bbox edge-to-edge distance)
            dx = max(0, max(tb[0] - icon_bbox[2], icon_bbox[0] - tb[2]))
            dy = max(0, max(tb[1] - icon_bbox[3], icon_bbox[1] - tb[3]))
            if dx < MERGER_PROXIMITY_THRESHOLD and dy < MERGER_PROXIMITY_THRESHOLD:
                has_text_nearby = True

        elem = {
            "type": "icon",
            "bbox": icon_bbox,
            "content": "",
            "confidence": icon.get("confidence", 1.0),
        }
        merged.append(elem)

        if not has_text_overlap and not has_text_nearby:
            icons_needing_classify.append(elem)

    return merged, icons_needing_classify
