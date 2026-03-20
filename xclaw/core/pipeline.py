"""Two-layer vision pipeline: L1 perception → L2-lite spatial."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Column


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

    Args:
        image_path: Path to screenshot image.
        skip_l2: Stop after L1 (perception only).

    Returns:
        PipelineResult with timing information.
    """
    timing: dict[str, int] = {}

    # ── L1: Perception ──
    l1_start = time.perf_counter_ns()

    # Image load
    t = time.perf_counter_ns()
    import numpy as np
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size
    screenshot = np.array(img)
    timing["image_load_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    # Engine init (lazy model load)
    t = time.perf_counter_ns()
    from xclaw.core.perception.engine import PerceptionEngine

    engine = PerceptionEngine.get_instance()
    engine._ensure_models()
    timing["engine_init_ms"] = (time.perf_counter_ns() - t) // 1_000_000
    backend = getattr(engine, "_backend", None)
    if backend and hasattr(backend, "load_timing") and backend.load_timing:
        timing["model_load"] = dict(backend.load_timing)

    # YOLO icon detection
    t = time.perf_counter_ns()
    icon_boxes = engine.detect_icons(screenshot)
    timing["yolo_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    # OCR text detection
    t = time.perf_counter_ns()
    text_boxes = engine.detect_text(screenshot)
    timing["ocr_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    # Spatial fusion
    t = time.perf_counter_ns()
    from xclaw.core.perception.merger import fuse_results, merge_elements

    fused, icons_needing_classify = fuse_results(icon_boxes, text_boxes)
    timing["fuse_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    # Conditional classification for text-less icons (SigLIP 2)
    t = time.perf_counter_ns()
    classify_count = 0
    if engine.classify_enabled and icons_needing_classify:
        from xclaw.config import CLASSIFY_CONFIDENCE_THRESHOLD, CLASSIFY_TOP2_GAP_THRESHOLD

        results = engine.classify_icons(screenshot, icons_needing_classify)
        classify_count = len(icons_needing_classify)
        for elem, r in zip(icons_needing_classify, results):
            if (r["confidence"] >= CLASSIFY_CONFIDENCE_THRESHOLD
                    and r.get("gap", 1.0) >= CLASSIFY_TOP2_GAP_THRESHOLD):
                elem["content"] = r["label"]
    timing["classify_ms"] = (time.perf_counter_ns() - t) // 1_000_000
    timing["classify_count"] = classify_count

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

    # Merge dedup
    t = time.perf_counter_ns()
    elements = merge_elements(elements)
    timing["merge_ms"] = (time.perf_counter_ns() - t) // 1_000_000

    timing["l1_ms"] = (time.perf_counter_ns() - l1_start) // 1_000_000

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
