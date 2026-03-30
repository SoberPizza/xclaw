"""Vision pipeline: perception + coordinate sorting."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from xclaw.core.perception.types import RawElement


@dataclass(slots=True)
class PipelineResult:
    """Full output of the vision pipeline."""

    elements: list[RawElement] = field(default_factory=list)
    resolution: tuple[int, int] = (0, 0)
    image_path: str = ""
    timing: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to the JSON format consumed by LLM."""
        return {
            "elements": [
                {
                    "id": e.id,
                    "type": e.type,
                    "bbox": list(e.bbox),
                    "center": list(e.center),
                    "content": e.content,
                }
                for e in self.elements
            ],
            "resolution": list(self.resolution),
            "timing": self.timing,
        }


def run_pipeline(image_path: str) -> PipelineResult:
    """Execute the vision pipeline.

    Args:
        image_path: Path to screenshot image.

    Returns:
        PipelineResult with timing information.
    """
    timing: dict[str, int] = {}

    t0 = time.perf_counter_ns()

    from xclaw.core.perception.engine import PerceptionEngine

    engine = PerceptionEngine.get_instance()

    import numpy as np
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size
    screenshot = np.array(img)

    # Run detection + OCR + fusion
    icon_boxes = engine.detect_icons(screenshot)
    text_boxes = engine.detect_text(screenshot)

    from xclaw.core.perception.merger import fuse_results, merge_elements

    fused, icons_needing_classification = fuse_results(icon_boxes, text_boxes)

    # Icon classification for text-less icons
    if engine.classifier_enabled and icons_needing_classification:
        labels = engine.classify_icons(screenshot, icons_needing_classification)
        for elem, label in zip(icons_needing_classification, labels):
            elem["content"] = label

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

    # Dedup + sort by y→x (reading order)
    elements = merge_elements(elements)
    elements = sorted(elements, key=lambda e: (e.center[1], e.center[0]))
    for i, e in enumerate(elements):
        e.id = i

    timing["ms"] = (time.perf_counter_ns() - t0) // 1_000_000

    return PipelineResult(
        elements=elements,
        resolution=(w, h),
        image_path=image_path,
        timing=timing,
    )
