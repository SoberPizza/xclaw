"""Page context inference from spatial and semantic analysis."""

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Region
from xclaw.core.semantic.types import Component, ComponentType, PageContext


def infer_context(
    elements: list[RawElement],
    regions: list[Region],
    components: list[Component],
    resolution: tuple[int, int],
) -> PageContext:
    """Infer high-level page context.

    - scroll_position: based on first/last element position
    - modal_open: whether a Modal component was detected
    - loading: very few elements or contains "Loading" text
    - partial_cards: cards with bbox extending beyond viewport edges
    """
    w, h = resolution

    # scroll_position
    scroll_position = "unknown"
    if elements:
        min_y = min(e.bbox[1] for e in elements)
        max_y = max(e.bbox[3] for e in elements)

        near_top = min_y < h * 0.05
        near_bottom = max_y > h * 0.95

        if near_top and near_bottom:
            scroll_position = "middle"  # content fills viewport
        elif near_top:
            scroll_position = "top"
        elif near_bottom:
            scroll_position = "bottom"
        else:
            scroll_position = "middle"

    # modal_open
    modal_open = any(c.type == ComponentType.MODAL for c in components)

    # loading
    loading = False
    if len(elements) < 5:
        loading = True
    elif any(
        "loading" in e.content.lower()
        for e in elements
        if e.type == "text"
    ):
        loading = True

    # partial_cards: cards clipped at viewport edges
    partial_cards: list[str] = []
    for comp in components:
        if comp.type != ComponentType.CARD:
            continue
        if comp.bbox[1] < 5:  # top edge clipped
            if "top" not in partial_cards:
                partial_cards.append("top")
        if comp.bbox[3] > h - 5:  # bottom edge clipped
            if "bottom" not in partial_cards:
                partial_cards.append("bottom")

    return PageContext(
        scroll_position=scroll_position,
        modal_open=modal_open,
        loading=loading,
        partial_cards=partial_cards,
    )
