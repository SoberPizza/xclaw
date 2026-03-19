"""Two-layer vision pipeline: L1 perception → L2-lite spatial."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Column

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineResult:
    """Full output of the vision pipeline."""

    # L1
    elements: list[RawElement] = field(default_factory=list)
    resolution: tuple[int, int] = (0, 0)
    image_path: str = ""

    # L2 (None if skipped)
    columns: list[Column] | None = None
    reading_order: list[int] | None = None

    # Timing
    timing: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to the JSON format consumed by LLM."""
        result: dict = {}

        # Plugin
        

        if self.columns is not None:
            # L2 output: layout + annotated elements
            elem_col_map: dict[int, int] = {}
            for col in self.columns:
                for eid in col.element_ids:
                    elem_col_map[eid] = col.id

            text_count = sum(1 for e in self.elements if e.type == "text")
            icon_count = sum(1 for e in self.elements if e.type == "icon")

            result["layout"] = {
                "columns": [
                    {
                        "id": col.id,
                        "x_range": [col.x_start, col.x_end],
                        "width_pct": round((col.x_end - col.x_start) * 100 / self.resolution[0])
                        if self.resolution[0] > 0 else 0,
                        "element_count": len(col.element_ids),
                    }
                    for col in self.columns
                ],
                "total_elements": len(self.elements),
                "text_count": text_count,
                "icon_count": icon_count,
            }

            order = self.reading_order or [e.id for e in self.elements]
            elem_by_id = {e.id: e for e in self.elements}
            result["elements"] = [
                {
                    "id": eid,
                    "type": elem_by_id[eid].type,
                    "bbox": list(elem_by_id[eid].bbox),
                    "center": list(elem_by_id[eid].center),
                    "content": elem_by_id[eid].content,
                    "col": elem_col_map.get(eid),
                }
                for eid in order
                if eid in elem_by_id
            ]
        else:
            # L1-only output
            result["elements"] = [
                {
                    "id": e.id,
                    "type": e.type,
                    "bbox": list(e.bbox),
                    "center": list(e.center),
                    "content": e.content,
                }
                for e in self.elements
            ]
            result["resolution"] = list(self.resolution)

        # Timing
        result["timing"] = self.timing

        return result


def run_pipeline(
    image_path: str,
    *,
    skip_l2: bool = False,
) -> PipelineResult:
    """Execute the two-layer vision pipeline.

    For CLI and agent callers, prefer ``schedule()`` from
    ``xclaw.core.context.scheduler`` which adds smart caching,
    incremental perception, and post-action verification.
    Use ``run_pipeline()`` directly only when you need a guaranteed
    full pipeline run without caching semantics (e.g., benchmarks,
    debug visualization, forced re-perception).

    Args:
        image_path: Path to screenshot image.
        skip_l2: Stop after L1 (perception only).

    Returns:
        PipelineResult with timing information.
    """
    timing: dict[str, int] = {}

    # ── L1: Perception ──
    t0 = time.perf_counter_ns()

    from xclaw.core.perception.engine import PerceptionEngine

    engine = PerceptionEngine.get_instance()

    # Use the engine's full_look which handles YOLO + OCR + Florence-2
    import numpy as np
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size
    screenshot = np.array(img)

    # Run detection + OCR + fusion
    degraded: list[str] = []

    try:
        icon_boxes = engine.detect_icons(screenshot)
    except Exception as e:
        logger.warning("YOLO detection failed in pipeline, continuing: %s", e)
        icon_boxes = []
        degraded.append("yolo")

    try:
        text_boxes = engine.detect_text(screenshot)
    except Exception as e:
        logger.warning("OCR failed in pipeline, continuing: %s", e)
        text_boxes = []
        degraded.append("ocr")

    from xclaw.core.perception.merger import fuse_results, merge_elements

    fused, icons_needing_caption = fuse_results(icon_boxes, text_boxes)

    # Conditional caption
    try:
        if (
            engine.caption_enabled
            and engine.caption_conditional
            and icons_needing_caption
        ):
            captions = engine.caption_icons(screenshot, icons_needing_caption)
            for elem, cap in zip(icons_needing_caption, captions):
                elem["content"] = cap
    except Exception as e:
        logger.warning("Caption failed in pipeline, continuing: %s", e)
        degraded.append("caption")

    # Convert fused dicts to RawElement
    elements = []
    for i, elem in enumerate(fused):
        bbox = elem["bbox"]
        if isinstance(bbox, list):
            bbox = tuple(bbox)
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        elements.append(RawElement(
            id=i,
            type=elem.get("type", "unknown"),
            bbox=bbox,
            center=(cx, cy),
            content=elem.get("content", ""),
            confidence=elem.get("confidence", 1.0),
        ))

    # Apply merge dedup
    elements = merge_elements(elements)


    timing["l1_ms"] = (time.perf_counter_ns() - t0) // 1_000_000

    if skip_l2:
        return PipelineResult(
            elements=elements,
            resolution=(w, h),
            image_path=image_path,
            timing=timing,
        )

    # ── L2: Column Detection + Reading Order ──
    t1 = time.perf_counter_ns()

    from xclaw.core.spatial.column_detector import detect_columns
    from xclaw.core.spatial.reading_order import sort_reading_order

    columns = detect_columns(elements, resolution=(w, h))
    reading_order = sort_reading_order(elements, columns)

    timing["l2_ms"] = (time.perf_counter_ns() - t1) // 1_000_000

    result = PipelineResult(
        elements=elements,
        resolution=(w, h),
        image_path=image_path,
        columns=columns,
        reading_order=reading_order,
        timing=timing,
    )

    return result
