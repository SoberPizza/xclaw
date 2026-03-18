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

    # Plugin
    plugin_name: str | None = None

    # Timing
    timing: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to the JSON format consumed by LLM."""
        result: dict = {}

        # Plugin
        result["plugin"] = self.plugin_name

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
    plugin=None,
) -> PipelineResult:
    """Execute the two-layer vision pipeline.

    Args:
        image_path: Path to screenshot image.
        skip_l2: Stop after L1 (perception only).
        plugin: Optional SitePlugin instance for enhancement hooks.

    Returns:
        PipelineResult with timing information.
    """
    timing: dict[str, int] = {}

    # ── L1: Perception ──
    t0 = time.perf_counter_ns()

    from xclaw.core.perception.omniparser import ScreenParser
    from xclaw.core.perception.merger import merge_elements

    parser = ScreenParser()
    raw_elements, resolution = parser.parse_raw(image_path)
    elements = merge_elements(raw_elements)

    if plugin:
        elements = plugin.enhance_anchors(elements, resolution)

    timing["l1_ms"] = (time.perf_counter_ns() - t0) // 1_000_000

    if skip_l2:
        return PipelineResult(
            elements=elements,
            resolution=resolution,
            image_path=image_path,
            plugin_name=plugin.__class__.__name__ if plugin else None,
            timing=timing,
        )

    # ── L2: Column Detection + Reading Order ──
    t1 = time.perf_counter_ns()

    from xclaw.core.spatial.column_detector import detect_columns
    from xclaw.core.spatial.reading_order import sort_reading_order

    columns = detect_columns(elements, resolution=resolution)
    reading_order = sort_reading_order(elements, columns)

    timing["l2_ms"] = (time.perf_counter_ns() - t1) // 1_000_000

    result = PipelineResult(
        elements=elements,
        resolution=resolution,
        image_path=image_path,
        columns=columns,
        reading_order=reading_order,
        plugin_name=plugin.__class__.__name__ if plugin else None,
        timing=timing,
    )

    if plugin:
        result = plugin.post_process(result)
        result.timing = timing

    return result
