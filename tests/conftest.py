"""Shared fixtures for integration tests and benchmarks."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from xclaw.core.context.state import ContextState
from xclaw.core.perception.types import RawElement
from xclaw.core.pipeline import PipelineResult
from xclaw.core.context.glance import _run_l2, _elements_to_dicts

# ── Directories ──

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "screenshots"


# ── Helpers ──

def _elem(
    id: int,
    type: str = "text",
    bbox: tuple[int, int, int, int] = (0, 0, 100, 20),
    content: str = "test",
    confidence: float = 1.0,
    source: str = "",
) -> RawElement:
    return RawElement(
        id=id,
        type=type,
        bbox=bbox,
        center=((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2),
        content=content,
        confidence=confidence,
        source=source,
    )


def _build_elements(n: int = 10, resolution: tuple[int, int] = (1920, 1080)) -> list[RawElement]:
    """Build a grid of synthetic elements spread across the resolution."""
    w, h = resolution
    elems = []
    cols = 5
    for i in range(n):
        col = i % cols
        row = i // cols
        x1 = col * (w // cols) + 10
        y1 = row * 40 + 10
        x2 = x1 + 120
        y2 = y1 + 20
        elems.append(_elem(i, bbox=(x1, y1, x2, y2), content=f"item_{i}"))
    return elems


# ── Fixtures ──

@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Redirect CONTEXT_STATE_PATH to tmp_path so tests don't pollute disk."""
    state_path = tmp_path / ".context_state.json"
    monkeypatch.setattr("xclaw.core.context.state.CONTEXT_STATE_PATH", state_path)
    return tmp_path


@pytest.fixture
def screenshot_paths():
    """Return sorted list of real screenshots from the screenshots/ dir."""
    paths = sorted(SCREENSHOTS_DIR.glob("screen_*.png"))
    if len(paths) < 2:
        pytest.skip("Need at least 2 screenshots in screenshots/ directory")
    return paths


@pytest.fixture
def screenshot_pair(screenshot_paths):
    """Return (path[0], path[1]) — two consecutive screenshots."""
    return (str(screenshot_paths[0]), str(screenshot_paths[1]))


@pytest.fixture
def screenshot_triple(screenshot_paths):
    """Return (path[0], path[1], path[2]) — three consecutive screenshots."""
    if len(screenshot_paths) < 3:
        pytest.skip("Need at least 3 screenshots")
    return (str(screenshot_paths[0]), str(screenshot_paths[1]), str(screenshot_paths[2]))


@pytest.fixture
def mock_take_screenshot(monkeypatch):
    """Return a helper to set the next screenshot path for scheduler.take_screenshot."""
    _next_path: list[str] = []

    def _fake_screenshot():
        path = _next_path.pop(0) if _next_path else "/dev/null"
        return {"image_path": path}

    patcher = patch("xclaw.core.context.scheduler.take_screenshot", side_effect=_fake_screenshot)
    mock = patcher.start()

    class Helper:
        def set_next(self, path: str):
            _next_path.append(path)

        def set_many(self, paths: list[str]):
            _next_path.extend(paths)

    yield Helper()
    patcher.stop()


@pytest.fixture
def mock_run_pipeline(monkeypatch):
    """Patch run_pipeline in both scheduler and glance; return pre-built PipelineResult.

    The mock builds a PipelineResult by running _run_l2 on CPU with synthetic elements,
    so L2 spatial layer executes for real.
    """
    elements = _build_elements(10, (1920, 1080))
    result = _run_l2(elements, (1920, 1080), "synthetic.png")
    result_dict = result.to_dict()

    def _fake_run_pipeline(image_path, **kwargs):
        r = _run_l2(elements, (1920, 1080), image_path)
        return r

    patcher_sched = patch("xclaw.core.context.scheduler.run_pipeline", side_effect=_fake_run_pipeline)
    patcher_glance = patch("xclaw.core.context.glance.run_pipeline", side_effect=_fake_run_pipeline)
    mock_s = patcher_sched.start()
    mock_g = patcher_glance.start()

    class Info:
        pipeline_result = result
        pipeline_dict = result_dict
        raw_elements = elements

    yield Info()
    patcher_sched.stop()
    patcher_glance.stop()


@pytest.fixture
def mock_crop_and_parse(monkeypatch):
    """Patch glance._crop_and_parse to return a filtered subset of cached elements."""

    def _fake_crop(image_path, region, resolution, margin=20, *, parser=None):
        # Return a couple of synthetic elements within the region
        x1, y1, x2, y2 = region
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return [
            _elem(900, bbox=(x1 + 5, y1 + 5, x2 - 5, y2 - 5), content="parsed_region"),
        ]

    monkeypatch.setattr("xclaw.core.context.glance._crop_and_parse", _fake_crop)


# ── Synthetic image helpers ──

@pytest.fixture
def make_gray_image(tmp_path):
    """Factory fixture: create a grayscale image of given size and color."""

    def _make(color: int, width: int = 1920, height: int = 1080, name: str = "img.png") -> str:
        img = np.full((height, width), color, dtype=np.uint8)
        path = str(tmp_path / name)
        cv2.imwrite(path, img)
        return path

    return _make


@pytest.fixture
def make_image_with_rect(tmp_path):
    """Factory: base color image with a filled rectangle (for minor diff testing)."""

    def _make(
        bg_color: int = 128,
        rect_color: int = 255,
        rect: tuple[int, int, int, int] = (100, 100, 300, 200),
        width: int = 1920,
        height: int = 1080,
        name: str = "rect.png",
    ) -> str:
        img = np.full((height, width), bg_color, dtype=np.uint8)
        x1, y1, x2, y2 = rect
        img[y1:y2, x1:x2] = rect_color
        path = str(tmp_path / name)
        cv2.imwrite(path, img)
        return path

    return _make
