"""SitePlugin abstract base class.

Five hook points corresponding to pipeline intervention stages:
1. enhance_anchors — after L1, before L2
2. enhance_grouping — after block segmentation
3. classify_card — during L3 card detection
4. classify_page — after L3 region classification
5. post_process — after full pipeline
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclaw.core.perception.types import RawElement
    from xclaw.core.spatial.types import Block, Row, Region
    from xclaw.core.semantic.types import PageContext
    from xclaw.core.pipeline import PipelineResult


class SitePlugin(ABC):
    """Base class for site-specific pipeline plugins.

    Subclass this and implement `match()` to create a site-specific plugin.
    All hook methods have no-op defaults — override only what you need.
    """

    @abstractmethod
    def match(self, url: str = "", domain: str = "") -> bool:
        """Return True if this plugin should handle the given URL/domain."""
        ...

    def enhance_anchors(
        self,
        elements: list[RawElement],
        resolution: tuple[int, int],
    ) -> list[RawElement]:
        """Hook after L1: adjust or add anchor elements."""
        return elements

    def enhance_grouping(
        self,
        blocks: list[Block],
        rows: list[Row],
        elements: list[RawElement],
    ) -> list[Block]:
        """Hook after block segmentation: adjust block boundaries."""
        return blocks

    def classify_card(
        self,
        block: Block,
        elements: list[RawElement],
    ) -> str | None:
        """Hook during L3: return a card subtype or None to skip."""
        return None

    def classify_page(
        self,
        regions: list[Region],
        context: PageContext,
    ) -> str | None:
        """Hook after L3: return a page type label or None."""
        return None

    def post_process(self, result: PipelineResult) -> PipelineResult:
        """Hook after full pipeline: final adjustments."""
        return result
