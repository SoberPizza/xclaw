"""L2 spatial aggregation types."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Row:
    """A horizontal row of elements sharing similar y-center."""

    id: int
    y_center: float
    y_top: int
    y_bottom: int
    element_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Block:
    """A vertical group of consecutive rows separated by significant gaps."""

    id: int
    y_start: int
    y_end: int
    row_ids: list[int] = field(default_factory=list)
    gap_above: float = 0.0


@dataclass(slots=True)
class Column:
    """A vertical strip of elements aligned on the same x1 coordinate."""

    id: int
    x_start: int
    x_end: int
    element_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Region:
    """A classified page region (header / footer / sidebar / main)."""

    id: int
    role: str  # "header" | "footer" | "sidebar" | "main"
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    block_ids: list[int] = field(default_factory=list)
    pattern: str | None = None  # "feed" | "list" | None
