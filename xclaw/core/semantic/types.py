"""L3 semantic types."""

from dataclasses import dataclass, field
from enum import Enum


class ComponentType(Enum):
    CARD = "card"
    ACTION_ROW = "action_row"
    NAVIGATION = "navigation"
    SEARCH_BOX = "search_box"
    MODAL = "modal"
    INPUT_FIELD = "input_field"


@dataclass(slots=True)
class Component:
    """A detected UI component with semantic meaning."""

    id: int
    type: ComponentType
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    element_ids: list[int] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass(slots=True)
class PageContext:
    """High-level page state inferred from spatial + semantic analysis."""

    scroll_position: str = "unknown"  # "top" | "middle" | "bottom" | "unknown"
    modal_open: bool = False
    loading: bool = False
    partial_cards: list[str] = field(default_factory=list)  # ["top", "bottom"]
