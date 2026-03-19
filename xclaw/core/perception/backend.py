"""PerceptionBackend protocol — abstracts detection, OCR, and captioning."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from xclaw.core.perception.types import TextBox


@runtime_checkable
class PerceptionBackend(Protocol):
    """Contract that any perception backend must satisfy.

    Three granular methods (not a single ``perceive()``) because some
    callers (e.g. glance) need only detection + OCR without caption.
    """

    def load_models(self) -> None:
        """Ensure all underlying models are loaded and ready."""
        ...

    def detect_icons(self, image: np.ndarray, conf: float = 0.3) -> list[dict]:
        """Run icon/UI-element detection (e.g. YOLO).

        Returns list of dicts with at least ``bbox`` and ``confidence`` keys.
        """
        ...

    def detect_text(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        """Run OCR on *image*.

        Returns list of :class:`TextBox` instances.
        """
        ...

    def caption_icons(
        self, image: np.ndarray, icon_elements: list[dict]
    ) -> list[str]:
        """Generate short descriptions for icon regions.

        Args:
            image: Full screenshot as numpy array.
            icon_elements: Elements needing caption (must have ``bbox`` key).

        Returns:
            One description string per element.
        """
        ...

    @property
    def caption_enabled(self) -> bool:
        """Whether the caption model is available and configured."""
        ...

    @property
    def caption_conditional(self) -> bool:
        """Whether caption should only run for icons without text overlay."""
        ...
