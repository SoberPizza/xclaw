"""Three-layer vision pipeline: L1 perception → L2 spatial → L3 semantic."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Row, Block, Column, Region
from xclaw.core.semantic.types import Component, ComponentType, PageContext


@dataclass(slots=True)
class PipelineResult:
    """Full output of the vision pipeline."""

    # L1
    elements: list[RawElement] = field(default_factory=list)
    resolution: tuple[int, int] = (0, 0)
    image_path: str = ""

    # L2 (None if skipped)
    rows: list[Row] | None = None
    blocks: list[Block] | None = None
    columns: list[Column] | None = None
    regions: list[Region] | None = None
    patterns: dict[int, str] | None = None

    # L3 (None if skipped)
    components: list[Component] | None = None
    context: PageContext | None = None

    # Plugin
    plugin_name: str | None = None

    # Timing
    timing: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to the JSON format consumed by LLM."""
        result: dict = {}

        # Plugin
        result["plugin"] = self.plugin_name

        # Page layout (L2)
        if self.regions is not None:
            layout = "single"
            if self.columns and len(self.columns) >= 3:
                layout = "three-column"
            elif self.columns and len(self.columns) == 2:
                layout = "two-column"

            regions_dict: dict[str, dict] = {}
            for region in self.regions:
                entry = {
                    "bbox": list(region.bbox),
                    "block_ids": region.block_ids,
                }
                if region.pattern:
                    entry["pattern"] = region.pattern
                # Group by role, handle multiple of same role
                key = region.role
                if key in regions_dict:
                    key = f"{region.role}_{region.id}"
                regions_dict[key] = entry

            scroll_pos = self.context.scroll_position if self.context else "unknown"

            result["page"] = {
                "layout": layout,
                "regions": regions_dict,
                "scroll_position": scroll_pos,
            }

            if self.context and self.context.modal_open:
                result["page"]["modal_open"] = True
            if self.context and self.context.loading:
                result["page"]["loading"] = True

        # Components (L3)
        if self.components is not None:
            comp_dict: dict[str, list | dict] = {}
            for comp in self.components:
                key = comp.type.value
                entry = {
                    "id": comp.id,
                    "bbox": list(comp.bbox),
                    "element_ids": comp.element_ids,
                }
                if comp.properties:
                    entry["properties"] = comp.properties

                if key in ("card",):
                    # Cards are always a list
                    comp_dict.setdefault("cards", []).append(entry)
                elif key in comp_dict:
                    # Multiple of same type → make list
                    existing = comp_dict[key]
                    if isinstance(existing, dict):
                        comp_dict[key] = [existing, entry]
                    else:
                        existing.append(entry)
                else:
                    comp_dict[key] = entry

            result["components"] = comp_dict

        # Feed pattern
        if self.patterns:
            feed_blocks = [bid for bid, pat in self.patterns.items() if pat == "feed"]
            list_blocks = [bid for bid, pat in self.patterns.items() if pat == "list"]
            if feed_blocks or list_blocks:
                result["feed_pattern"] = {
                    "detected": True,
                    "card_count": len(feed_blocks) + len(list_blocks),
                }
        if "feed_pattern" not in result and self.patterns is not None:
            result["feed_pattern"] = {"detected": False, "card_count": 0}

        # Partial cards
        if self.context and self.context.partial_cards:
            result.setdefault("page", {})["partial_cards"] = self.context.partial_cards

        # Timing
        result["timing"] = self.timing

        # Fallback: L1-only output
        if self.regions is None and self.components is None:
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

        return result


def run_pipeline(
    image_path: str,
    *,
    skip_l2: bool = False,
    skip_l3: bool = False,
    plugin=None,
) -> PipelineResult:
    """Execute the three-layer vision pipeline.

    Args:
        image_path: Path to screenshot image.
        skip_l2: Stop after L1 (perception only).
        skip_l3: Stop after L2 (perception + spatial).
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

    # ── L2: Spatial Aggregation ──
    t1 = time.perf_counter_ns()

    from xclaw.core.spatial.row_detector import detect_rows
    from xclaw.core.spatial.block_segmenter import segment_blocks
    from xclaw.core.spatial.column_detector import detect_columns
    from xclaw.core.spatial.region_classifier import classify_regions
    from xclaw.core.spatial.pattern_detector import detect_patterns

    rows = detect_rows(elements)
    blocks = segment_blocks(rows, resolution)

    if plugin:
        blocks = plugin.enhance_grouping(blocks, rows, elements)

    columns = detect_columns(elements, resolution=resolution)
    regions = classify_regions(blocks, columns, resolution)
    patterns = detect_patterns(blocks, rows, elements)

    # Apply patterns to regions
    pattern_block_ids = set(patterns.keys())
    for region in regions:
        for bid in region.block_ids:
            if bid in pattern_block_ids:
                region.pattern = patterns[bid]

    timing["l2_ms"] = (time.perf_counter_ns() - t1) // 1_000_000

    if skip_l3:
        return PipelineResult(
            elements=elements,
            resolution=resolution,
            image_path=image_path,
            rows=rows,
            blocks=blocks,
            columns=columns,
            regions=regions,
            patterns=patterns,
            plugin_name=plugin.__class__.__name__ if plugin else None,
            timing=timing,
        )

    # ── L3: Semantic Annotation ──
    t2 = time.perf_counter_ns()

    from xclaw.core.semantic.universal import detect_components
    from xclaw.core.semantic.context import infer_context

    components = detect_components(elements, blocks, rows, regions, resolution)
    context = infer_context(elements, regions, components, resolution)

    if plugin:
        result = PipelineResult(
            elements=elements,
            resolution=resolution,
            image_path=image_path,
            rows=rows,
            blocks=blocks,
            columns=columns,
            regions=regions,
            patterns=patterns,
            components=components,
            context=context,
            plugin_name=plugin.__class__.__name__,
            timing=timing,
        )
        result = plugin.post_process(result)
        timing["l3_ms"] = (time.perf_counter_ns() - t2) // 1_000_000
        result.timing = timing
        return result

    timing["l3_ms"] = (time.perf_counter_ns() - t2) // 1_000_000

    return PipelineResult(
        elements=elements,
        resolution=resolution,
        image_path=image_path,
        rows=rows,
        blocks=blocks,
        columns=columns,
        regions=regions,
        patterns=patterns,
        components=components,
        context=context,
        plugin_name=None,
        timing=timing,
    )
