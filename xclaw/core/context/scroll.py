"""Scroll offset tracking via ORB feature matching."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from xclaw.core.perception.types import RawElement


@dataclass
class ScrollAnalysis:
    """Result of scroll offset analysis."""

    offset_y: int  # Positive = scrolled down, negative = scrolled up
    confidence: float  # 0-1, based on match quality
    matched_points: int
    new_strip: tuple[int, int, int, int] | None  # bbox of newly visible area


def analyze_scroll(
    current_path: str,
    previous_path: str,
    resolution: tuple[int, int],
) -> ScrollAnalysis:
    """Estimate vertical scroll offset using ORB feature matching.

    Args:
        current_path: Path to current screenshot.
        previous_path: Path to previous screenshot.
        resolution: (width, height) of the screenshots.

    Returns:
        ScrollAnalysis with estimated y offset and new strip bbox.
    """
    prev = cv2.imread(previous_path, cv2.IMREAD_GRAYSCALE)
    curr = cv2.imread(current_path, cv2.IMREAD_GRAYSCALE)

    if prev is None or curr is None:
        return ScrollAnalysis(offset_y=0, confidence=0.0, matched_points=0, new_strip=None)

    # ORB feature detection
    orb = cv2.ORB_create(nfeatures=500)
    kp1, des1 = orb.detectAndCompute(prev, None)
    kp2, des2 = orb.detectAndCompute(curr, None)

    if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
        return ScrollAnalysis(offset_y=0, confidence=0.0, matched_points=0, new_strip=None)

    # BFMatcher with Hamming distance
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(des1, des2, k=2)

    # Lowe's ratio test
    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good.append(m)

    if len(good) < 3:
        return ScrollAnalysis(offset_y=0, confidence=0.0, matched_points=len(good), new_strip=None)

    # Extract y-offsets from matched keypoints
    y_offsets = []
    for m in good:
        pt1 = kp1[m.queryIdx].pt
        pt2 = kp2[m.trainIdx].pt
        y_offsets.append(pt1[1] - pt2[1])  # positive = scrolled down

    # Use median for robustness against outliers
    offset_y = int(np.median(y_offsets))

    # Confidence based on consistency of offsets
    if len(y_offsets) > 1:
        std = float(np.std(y_offsets))
        confidence = max(0.0, min(1.0, 1.0 - std / 100.0))
    else:
        confidence = 0.3

    # Determine new strip (the area that scrolled into view)
    w, h = resolution
    if offset_y > 0:
        # Scrolled down → new content at bottom
        new_strip = (0, h - offset_y, w, h)
    elif offset_y < 0:
        # Scrolled up → new content at top
        new_strip = (0, 0, w, -offset_y)
    else:
        new_strip = None

    # Clamp new_strip to valid bounds
    if new_strip is not None:
        new_strip = (
            max(0, new_strip[0]),
            max(0, new_strip[1]),
            min(w, new_strip[2]),
            min(h, new_strip[3]),
        )
        if new_strip[2] <= new_strip[0] or new_strip[3] <= new_strip[1]:
            new_strip = None

    return ScrollAnalysis(
        offset_y=offset_y,
        confidence=confidence,
        matched_points=len(good),
        new_strip=new_strip,
    )


def shift_elements(
    elements: list[RawElement],
    offset_y: int,
    resolution: tuple[int, int],
) -> list[RawElement]:
    """Shift cached element coordinates by scroll offset, discarding out-of-viewport.

    Args:
        elements: Cached elements to shift.
        offset_y: Positive = scrolled down (elements move up by this amount).
        resolution: (width, height) for viewport bounds.

    Returns:
        Shifted elements that remain within the viewport.
    """
    w, h = resolution
    shifted = []
    for elem in elements:
        new_bbox = (
            elem.bbox[0],
            elem.bbox[1] - offset_y,
            elem.bbox[2],
            elem.bbox[3] - offset_y,
        )
        # Keep only if still within viewport
        if new_bbox[3] > 0 and new_bbox[1] < h:
            new_center = (elem.center[0], elem.center[1] - offset_y)
            shifted.append(RawElement(
                id=elem.id, type=elem.type, bbox=new_bbox,
                center=new_center, content=elem.content,
                confidence=elem.confidence, source=elem.source,
            ))
    return shifted
