"""L1 raw element types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawElement:
    """A single UI element detected by OmniParser.

    Frozen to guarantee L2 never accidentally mutates L1 output.
    Tuples (not lists) for hashability and cache-friendliness.
    """

    id: int
    type: str  # "text" | "icon"
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) pixels
    center: tuple[int, int]
    content: str
    confidence: float = 1.0
    source: str = ""  # OmniParser source tag
