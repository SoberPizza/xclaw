"""Performance benchmarks — measure critical path latencies."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from xclaw.core.context.state import ContextState
from xclaw.core.context.peek import peek
from xclaw.core.context.predict import predict
from xclaw.core.context.scroll import analyze_scroll
from xclaw.core.context.glance import _run_l2_l3, _elements_to_dicts

from conftest import _elem, _build_elements, SCREENSHOTS_DIR

pytestmark = pytest.mark.bench


# ── Benchmark harness ──

def _bench(fn, *, warmup: int = 2, iterations: int = 20, label: str = ""):
    """Run *fn* repeatedly and print timing statistics."""
    for _ in range(warmup):
        fn()

    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)  # ms

    times.sort()
    p95_idx = int(len(times) * 0.95)
    stats = {
        "min": f"{min(times):.2f}ms",
        "mean": f"{statistics.mean(times):.2f}ms",
        "max": f"{max(times):.2f}ms",
        "p95": f"{times[p95_idx]:.2f}ms",
    }
    tag = f" [{label}]" if label else ""
    print(f"\n  BENCH{tag}: {stats}")
    return times


# ── Fixtures ──

@pytest.fixture
def identical_images(tmp_path):
    """Two identical gray images."""
    img = np.full((1080, 1920), 128, dtype=np.uint8)
    a = str(tmp_path / "ident_a.png")
    b = str(tmp_path / "ident_b.png")
    cv2.imwrite(a, img)
    cv2.imwrite(b, img)
    return a, b


@pytest.fixture
def synthetic_1080p_pair(tmp_path):
    """Two 1920×1080 images with ~5% pixel difference."""
    rng = np.random.default_rng(42)
    base = rng.integers(0, 256, (1080, 1920), dtype=np.uint8)
    modified = base.copy()
    # Add noise to a 5% region
    modified[100:200, 200:400] = rng.integers(0, 256, (100, 200), dtype=np.uint8)
    a = str(tmp_path / "synth_a.png")
    b = str(tmp_path / "synth_b.png")
    cv2.imwrite(a, base)
    cv2.imwrite(b, modified)
    return a, b


@pytest.fixture
def real_pair():
    """First two real screenshots, or skip."""
    paths = sorted(SCREENSHOTS_DIR.glob("screen_*.png"))
    if len(paths) < 2:
        pytest.skip("Need at least 2 real screenshots")
    return str(paths[0]), str(paths[1])


# ── Benchmarks ──

class TestBenchPeek:
    def test_bench_peek_identical(self, identical_images):
        a, b = identical_images
        state = ContextState(last_screenshot_path=a, confidence=0.7, last_perception_time=time.time())

        def run():
            peek(state, b)

        times = _bench(run, label="peek_identical")
        assert statistics.mean(times) < 100, "Identical-image peek should be fast"

    def test_bench_peek_different(self, real_pair):
        a, b = real_pair
        state = ContextState(last_screenshot_path=a, confidence=0.7, last_perception_time=time.time())

        def run():
            peek(state, b)

        times = _bench(run, label="peek_real_different")
        assert statistics.mean(times) < 500, "Real-image peek should complete < 500ms"

    def test_bench_peek_synthetic_1080p(self, synthetic_1080p_pair):
        a, b = synthetic_1080p_pair
        state = ContextState(last_screenshot_path=a, confidence=0.7, last_perception_time=time.time())

        def run():
            peek(state, b)

        _bench(run, label="peek_synthetic_1080p")


class TestBenchScroll:
    def test_bench_scroll_analysis(self, real_pair):
        a, b = real_pair

        def run():
            analyze_scroll(b, a, (1920, 1080))

        times = _bench(run, label="scroll_orb")
        assert statistics.mean(times) < 500, "ORB scroll analysis should be < 500ms"


class TestBenchSpatialSemantic:
    def test_bench_spatial_semantic(self):
        """Run L2+L3 CPU pipeline on pre-built elements."""
        elements = _build_elements(30, (1920, 1080))

        def run():
            _run_l2_l3(elements, (1920, 1080), "bench.png")

        times = _bench(run, label="l2_l3_cpu")
        assert statistics.mean(times) < 200, "L2+L3 CPU should be < 200ms"


class TestBenchStatePersistence:
    def test_bench_state_save_load(self, state_dir):
        """Save and load a ~50KB state JSON."""
        elements = _elements_to_dicts(_build_elements(100, (1920, 1080)))
        state = ContextState(
            last_screenshot_path="/tmp/bench.png",
            last_result_dict={"data": list(range(500))},
            last_perception_level="L3",
            last_perception_time=time.time(),
            cached_elements=elements,
            cached_resolution=(1920, 1080),
            confidence=0.9,
            consecutive_cheap_count=1,
        )

        def run():
            state.save()
            ContextState.load()

        times = _bench(run, label="state_save_load")
        assert statistics.mean(times) < 50, "State save+load should be < 50ms"


class TestBenchPredict:
    def test_bench_predict(self):
        """predict() 100 times — should be sub-0.1ms per call."""
        state = ContextState(
            last_perception_time=time.time() - 1.0,
            confidence=1.0,
            last_result_dict={"data": "cached"},
        )
        state.record_action("type", {"text": "x"})
        state.record_action("click", {"x": 10, "y": 20})

        def run():
            for _ in range(100):
                predict(state)

        times = _bench(run, iterations=10, label="predict_x100")
        per_call = statistics.mean(times) / 100
        print(f"  Per-call: {per_call:.4f}ms")
        assert per_call < 1.0, "predict() should be < 1ms per call"
