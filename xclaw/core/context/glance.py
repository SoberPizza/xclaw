"""L2 Glance — local incremental parse of changed regions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from xclaw.core.context.state import ContextState
from xclaw.core.pipeline import PipelineResult, run_pipeline
from xclaw.core.perception.types import RawElement
from xclaw.config import CONTEXT_GLANCE_FALLBACK_RATIO, CONTEXT_OVERLAP_DISCARD_THRESHOLD


@dataclass
class GlanceResult:
    """Result of L2 local incremental parse."""

    pipeline_result: PipelineResult
    merged_from_cache: int
    newly_parsed: int
    elapsed_ms: int


def _overlap_ratio(
    elem_bbox: tuple[int, int, int, int],
    region: tuple[int, int, int, int],
) -> float:
    """Fraction of elem_bbox overlapping with region."""
    x1 = max(elem_bbox[0], region[0])
    y1 = max(elem_bbox[1], region[1])
    x2 = min(elem_bbox[2], region[2])
    y2 = min(elem_bbox[3], region[3])
    if x1 >= x2 or y1 >= y2:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    area = (elem_bbox[2] - elem_bbox[0]) * (elem_bbox[3] - elem_bbox[1])
    return inter / area if area > 0 else 0.0


def _elements_from_dicts(dicts: list[dict]) -> list[RawElement]:
    """Reconstruct RawElement list from serialized dicts."""
    elems = []
    for d in dicts:
        elems.append(RawElement(
            id=d["id"],
            type=d["type"],
            bbox=tuple(d["bbox"]),
            center=tuple(d["center"]),
            content=d["content"],
            confidence=d.get("confidence", 1.0),
            source=d.get("source", ""),
        ))
    return elems


def _elements_to_dicts(elements: list[RawElement]) -> list[dict]:
    """Serialize RawElement list to dicts."""
    return [
        {
            "id": e.id,
            "type": e.type,
            "bbox": list(e.bbox),
            "center": list(e.center),
            "content": e.content,
            "confidence": e.confidence,
            "source": e.source,
        }
        for e in elements
    ]


def _crop_and_parse(
    image_path: str,
    region: tuple[int, int, int, int],
    resolution: tuple[int, int],
    margin: int = 20,
    *,
    parser=None,
) -> list[RawElement]:
    """Crop a region from the image, run OmniParser, map coords back to global.

    Args:
        image_path: Full screenshot path.
        region: (x1, y1, x2, y2) change region.
        resolution: (width, height) of full screenshot.
        margin: Pixel margin to add around the region.
        parser: Optional ScreenParser instance to reuse across calls.

    Returns:
        List of RawElement with global coordinates.
    """
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        return []

    h, w = img.shape[:2]
    x1 = max(0, region[0] - margin)
    y1 = max(0, region[1] - margin)
    x2 = min(w, region[2] + margin)
    y2 = min(h, region[3] + margin)

    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return []

    # Save crop to temp file for OmniParser
    import tempfile
    import os
    fd, crop_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    try:
        cv2.imwrite(crop_path, crop)
        if parser is None:
            from xclaw.core.perception.omniparser import ScreenParser
            parser = ScreenParser()
        raw_elements, _ = parser.parse_raw(crop_path)
    finally:
        if os.path.exists(crop_path):
            os.unlink(crop_path)

    # Map coordinates back to global
    global_elements = []
    for elem in raw_elements:
        gbbox = (
            elem.bbox[0] + x1,
            elem.bbox[1] + y1,
            elem.bbox[2] + x1,
            elem.bbox[3] + y1,
        )
        gcenter = (elem.center[0] + x1, elem.center[1] + y1)
        global_elements.append(RawElement(
            id=elem.id, type=elem.type, bbox=gbbox,
            center=gcenter, content=elem.content,
            confidence=elem.confidence, source=elem.source,
        ))

    return global_elements


def _run_l2(
    elements: list[RawElement],
    resolution: tuple[int, int],
    image_path: str,
) -> PipelineResult:
    """Run L2 column detection + reading order on a set of elements (CPU only)."""
    from xclaw.core.spatial.column_detector import detect_columns
    from xclaw.core.spatial.reading_order import sort_reading_order

    columns = detect_columns(elements, resolution=resolution)
    reading_order = sort_reading_order(elements, columns)

    return PipelineResult(
        elements=elements,
        resolution=resolution,
        image_path=image_path,
        columns=columns,
        reading_order=reading_order,
        timing={},
    )


def glance(
    screenshot_path: str,
    change_regions: list[tuple[int, int, int, int]],
    state: ContextState,
) -> GlanceResult:
    """Incremental parse: only re-parse changed regions, merge with cache.

    If total change area > 60% of screen, falls back to full pipeline.
    If last action was scroll, uses ORB feature matching for smarter region detection.

    Args:
        screenshot_path: Path to current screenshot.
        change_regions: Bboxes of changed areas from peek().
        state: Current context state with cached elements.

    Returns:
        GlanceResult with merged pipeline output.
    """
    t0 = time.perf_counter_ns()
    resolution = state.cached_resolution
    if resolution == (0, 0):
        resolution = (1920, 1080)

    # Check if last action was scroll → use ORB-based optimization
    last = state.last_action()
    if (last and last.action == "scroll"
            and state.last_screenshot_path and state.cached_elements):
        from xclaw.core.context.scroll import analyze_scroll, shift_elements

        scroll_result = analyze_scroll(screenshot_path, state.last_screenshot_path, resolution)
        if scroll_result.confidence > 0.3 and scroll_result.offset_y != 0:
            # Shift cached elements by scroll offset
            cached_raw = _elements_from_dicts(state.cached_elements)
            shifted = shift_elements(cached_raw, scroll_result.offset_y, resolution)

            # Only parse the new strip
            new_elements: list[RawElement] = []
            if scroll_result.new_strip:
                parsed = _crop_and_parse(screenshot_path, scroll_result.new_strip, resolution)
                new_elements.extend(parsed)
            all_elements = shifted + new_elements
            renumbered = []
            for i, elem in enumerate(all_elements):
                renumbered.append(RawElement(
                    id=i, type=elem.type, bbox=elem.bbox,
                    center=elem.center, content=elem.content,
                    confidence=elem.confidence, source=elem.source,
                ))

            from xclaw.core.perception.merger import merge_elements
            merged = merge_elements(renumbered)

            pipeline_result = _run_l2(merged, resolution, screenshot_path)
            elapsed = (time.perf_counter_ns() - t0) // 1_000_000
            pipeline_result.timing["glance_ms"] = elapsed
            pipeline_result.timing["scroll_offset"] = scroll_result.offset_y

            return GlanceResult(
                pipeline_result=pipeline_result,
                merged_from_cache=len(shifted),
                newly_parsed=len(new_elements),
                elapsed_ms=elapsed,
            )

    # Check if change area is too large → fall back to full pipeline
    screen_area = resolution[0] * resolution[1]
    change_area = sum(
        (r[2] - r[0]) * (r[3] - r[1]) for r in change_regions
    )
    if screen_area > 0 and change_area / screen_area > CONTEXT_GLANCE_FALLBACK_RATIO:
        result = run_pipeline(screenshot_path)
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        return GlanceResult(
            pipeline_result=result,
            merged_from_cache=0,
            newly_parsed=len(result.elements),
            elapsed_ms=elapsed,
        )

    # Parse each changed region (reuse a single parser instance)
    from xclaw.core.perception.omniparser import ScreenParser
    parser = ScreenParser()
    new_elements: list[RawElement] = []
    for region in change_regions:
        parsed = _crop_and_parse(screenshot_path, region, resolution, parser=parser)
        new_elements.extend(parsed)

    # Filter cached elements: keep those NOT overlapping with change regions
    cached_raw = _elements_from_dicts(state.cached_elements)
    kept = []
    for elem in cached_raw:
        overlaps = any(
            _overlap_ratio(elem.bbox, r) > CONTEXT_OVERLAP_DISCARD_THRESHOLD
            for r in change_regions
        )
        if not overlaps:
            kept.append(elem)

    # Merge: kept cache + new parsed
    all_elements = kept + new_elements
    # Renumber IDs
    renumbered = []
    for i, elem in enumerate(all_elements):
        renumbered.append(RawElement(
            id=i, type=elem.type, bbox=elem.bbox,
            center=elem.center, content=elem.content,
            confidence=elem.confidence, source=elem.source,
        ))

    # Deduplicate with merger
    from xclaw.core.perception.merger import merge_elements
    merged = merge_elements(renumbered)

    pipeline_result = _run_l2(merged, resolution, screenshot_path)

    elapsed = (time.perf_counter_ns() - t0) // 1_000_000
    pipeline_result.timing["glance_ms"] = elapsed

    return GlanceResult(
        pipeline_result=pipeline_result,
        merged_from_cache=len(kept),
        newly_parsed=len(new_elements),
        elapsed_ms=elapsed,
    )
