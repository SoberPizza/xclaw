"""L1 Peek — cv2 pixel diff with change region detection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from xclaw.config import (
    CONTEXT_DIFF_THRESHOLD_UNCHANGED, CONTEXT_DIFF_THRESHOLD_MINOR,
    CONTEXT_PIXEL_DIFF_THRESHOLD, CONTEXT_CONTOUR_MIN_AREA,
    CONTEXT_CONTOUR_MERGE_DISTANCE,
)
from xclaw.core.context.state import ContextState


@dataclass
class PeekResult:
    """Result of L1 pixel diff comparison."""

    changed: bool
    diff_ratio: float
    change_regions: list[tuple[int, int, int, int]]  # bboxes of changed areas
    screenshot_path: str
    elapsed_ms: int
    suggest_level: str = "L1"  # "L1" (no change) | "L2" (minor) | "L3" (major)


def _merge_nearby_contours(
    contours: list[np.ndarray],
    merge_distance: int = 20,
) -> list[tuple[int, int, int, int]]:
    """Merge contour bounding boxes that are close to each other."""
    if not contours:
        return []

    boxes = [cv2.boundingRect(c) for c in contours]
    # Convert (x, y, w, h) → (x1, y1, x2, y2)
    rects = [(x, y, x + w, y + h) for x, y, w, h in boxes]

    # Greedy merge: expand each rect by merge_distance, merge overlapping
    merged = True
    while merged:
        merged = False
        new_rects = []
        used = set()
        for i, r1 in enumerate(rects):
            if i in used:
                continue
            x1, y1, x2, y2 = r1
            for j, r2 in enumerate(rects):
                if j <= i or j in used:
                    continue
                # Check if expanded rects overlap
                if (x1 - merge_distance <= r2[2] and x2 + merge_distance >= r2[0] and
                        y1 - merge_distance <= r2[3] and y2 + merge_distance >= r2[1]):
                    x1 = min(x1, r2[0])
                    y1 = min(y1, r2[1])
                    x2 = max(x2, r2[2])
                    y2 = max(y2, r2[3])
                    used.add(j)
                    merged = True
            new_rects.append((x1, y1, x2, y2))
            used.add(i)
        rects = new_rects

    return rects


def peek(state: ContextState, screenshot_path: str) -> PeekResult:
    """Compare current screenshot against previous using cv2 pixel diff.

    Args:
        state: Current context state (contains last_screenshot_path).
        screenshot_path: Path to the newly taken screenshot.

    Returns:
        PeekResult with diff analysis.
    """
    t0 = time.perf_counter_ns()

    if not state.last_screenshot_path:
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        return PeekResult(
            changed=True, diff_ratio=1.0, change_regions=[],
            screenshot_path=screenshot_path, elapsed_ms=elapsed,
            suggest_level="L3",
        )

    try:
        prev_img = cv2.imread(state.last_screenshot_path, cv2.IMREAD_GRAYSCALE)
        curr_img = cv2.imread(screenshot_path, cv2.IMREAD_GRAYSCALE)
    except Exception:
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        return PeekResult(
            changed=True, diff_ratio=1.0, change_regions=[],
            screenshot_path=screenshot_path, elapsed_ms=elapsed,
            suggest_level="L3",
        )

    if prev_img is None or curr_img is None:
        elapsed = (time.perf_counter_ns() - t0) // 1_000_000
        return PeekResult(
            changed=True, diff_ratio=1.0, change_regions=[],
            screenshot_path=screenshot_path, elapsed_ms=elapsed,
            suggest_level="L3",
        )

    # Resize to match if needed
    if prev_img.shape != curr_img.shape:
        prev_img = cv2.resize(prev_img, (curr_img.shape[1], curr_img.shape[0]))

    # Absolute diff → threshold → contours
    diff = cv2.absdiff(prev_img, curr_img)
    _, thresh = cv2.threshold(diff, CONTEXT_PIXEL_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    changed_pixels = int(np.count_nonzero(thresh))
    diff_ratio = changed_pixels / total_pixels if total_pixels > 0 else 1.0

    # Find change regions
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Filter tiny contours (noise)
    contours = [c for c in contours if cv2.contourArea(c) > CONTEXT_CONTOUR_MIN_AREA]
    change_regions = _merge_nearby_contours(contours, merge_distance=CONTEXT_CONTOUR_MERGE_DISTANCE)

    # Determine suggestion
    changed = diff_ratio > CONTEXT_DIFF_THRESHOLD_UNCHANGED
    if diff_ratio < CONTEXT_DIFF_THRESHOLD_UNCHANGED:
        suggest = "L1"  # no meaningful change
    elif diff_ratio < CONTEXT_DIFF_THRESHOLD_MINOR:
        suggest = "L2"  # minor change → glance
    else:
        suggest = "L3"  # major change → full look

    elapsed = (time.perf_counter_ns() - t0) // 1_000_000

    return PeekResult(
        changed=changed,
        diff_ratio=round(diff_ratio, 4),
        change_regions=change_regions,
        screenshot_path=screenshot_path,
        elapsed_ms=elapsed,
        suggest_level=suggest,
    )
