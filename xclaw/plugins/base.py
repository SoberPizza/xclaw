"""SitePlugin abstract base class.

Three hook points corresponding to pipeline intervention stages:
1. enhance_anchors — after L1, before L2
2. post_process — after full pipeline
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclaw.core.perception.types import RawElement
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

    def post_process(self, result: PipelineResult) -> PipelineResult:
        """Hook after full pipeline: final adjustments."""
        return result
