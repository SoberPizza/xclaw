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
class Column:
    """A vertical strip of elements aligned on overlapping x-ranges."""

    id: int
    x_start: int
    x_end: int
    element_ids: list[int] = field(default_factory=list)
