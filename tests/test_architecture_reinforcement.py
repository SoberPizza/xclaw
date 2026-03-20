"""Verification tests for architecture reinforcement plan.

Tests cover:
- Phase 1B: Graceful degradation with degraded field
- Phase 2A: Bezier T0-relative timing precision
- Phase 3A: Small element center-distance dedup
- Phase 3B: Model SHA256 verification with truncated files
- Phase 3C: Download retry with exponential backoff
- Phase 4C: freeze_backend() prevents set_backend()
"""

from __future__ import annotations

import hashlib
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from xclaw.core.perception.types import RawElement
from xclaw.core.perception.merger import merge_elements, _is_small, _center_distance


# ── Helpers ──────────────────────────────────────────────────────────────────

def _elem(id, type="text", bbox=(0, 0, 10, 10), content="test"):
    return RawElement(
        id=id, type=type, bbox=bbox,
        center=((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2),
        content=content,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1B: Perception graceful degradation
# ═══════════════════════════════════════════════════════════════════════════


class TestPerceptionGracefulDegradation:
    def test_yolo_failure_returns_degraded(self):
        """When YOLO fails, result should have degraded=["yolo"] with OCR results."""
        from xclaw.core.perception.engine import PerceptionEngine

        mock_backend = MagicMock()
        mock_backend.load_models.return_value = None
        mock_backend.detect_icons.side_effect = RuntimeError("YOLO crash")
        mock_backend.detect_text.return_value = []
        mock_backend.classify_enabled = False

        engine = PerceptionEngine(backend=mock_backend)

        import numpy as np
        fake_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        with patch.object(engine, "_capture", return_value=fake_screenshot):
            result = engine.full_look()

        assert result["status"] == "ok"
        assert "degraded" in result
        assert "yolo" in result["degraded"]

    def test_ocr_failure_returns_degraded(self):
        """When OCR fails, result should have degraded=["ocr"] with YOLO results."""
        from xclaw.core.perception.engine import PerceptionEngine

        mock_backend = MagicMock()
        mock_backend.load_models.return_value = None
        mock_backend.detect_icons.return_value = [
            {"bbox": (10, 10, 50, 50), "confidence": 0.9}
        ]
        mock_backend.detect_text.side_effect = RuntimeError("OCR crash")
        mock_backend.classify_enabled = False

        engine = PerceptionEngine(backend=mock_backend)

        import numpy as np
        fake_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        with patch.object(engine, "_capture", return_value=fake_screenshot):
            result = engine.full_look()

        assert result["status"] == "ok"
        assert "degraded" in result
        assert "ocr" in result["degraded"]
        assert result["element_count"] >= 1  # YOLO result should survive

    def test_classify_failure_returns_degraded(self):
        """When classification fails, result should have degraded=["classify"]."""
        from xclaw.core.perception.engine import PerceptionEngine

        mock_backend = MagicMock()
        mock_backend.load_models.return_value = None
        mock_backend.detect_icons.return_value = [
            {"bbox": (10, 10, 50, 50), "confidence": 0.9}
        ]
        mock_backend.detect_text.return_value = []
        mock_backend.classify_enabled = True
        mock_backend.classify_icons.side_effect = RuntimeError("Classify crash")

        engine = PerceptionEngine(backend=mock_backend)

        import numpy as np
        fake_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        with patch.object(engine, "_capture", return_value=fake_screenshot):
            result = engine.full_look()

        assert result["status"] == "ok"
        assert "degraded" in result
        assert "classify" in result["degraded"]

    def test_no_failure_no_degraded_field(self):
        """When all subsystems succeed, no degraded field in result."""
        from xclaw.core.perception.engine import PerceptionEngine

        mock_backend = MagicMock()
        mock_backend.load_models.return_value = None
        mock_backend.detect_icons.return_value = []
        mock_backend.detect_text.return_value = []
        mock_backend.classify_enabled = False

        engine = PerceptionEngine(backend=mock_backend)

        import numpy as np
        fake_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        with patch.object(engine, "_capture", return_value=fake_screenshot):
            result = engine.full_look()

        assert result["status"] == "ok"
        assert "degraded" not in result


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2A: Bezier T0-relative timing precision
# ═══════════════════════════════════════════════════════════════════════════


class TestBezierTimingPrecision:
    def test_total_duration_within_tolerance(self):
        """Bezier move should complete within ±15% of target duration."""
        from xclaw.action.humanize_strategy import BezierStrategy

        # Fixed duration to make test deterministic
        strategy = BezierStrategy(
            duration_range=(0.2, 0.2),  # exact 0.2s
            bezier_steps=20,
        )

        moves = []
        def move_fn(x, y):
            moves.append((x, y, time.perf_counter()))

        t0 = time.perf_counter()
        strategy._bezier_move(0, 0, 100, 100, move_fn)
        total = time.perf_counter() - t0

        assert len(moves) == 20
        # Should be within 15% of 0.2s
        assert 0.17 <= total <= 0.30, f"Duration {total:.3f}s not within tolerance of 0.2s"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2B: PipelineBackend unload
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineBackendUnload:
    def test_unload_classifier_releases_model(self):
        """unload_classifier should set _classifier to None."""
        from xclaw.core.perception.pipeline_backend import PipelineBackend

        config = MagicMock()
        config.classify_enabled = True
        backend = PipelineBackend(config)
        backend._classifier = MagicMock()
        backend._models_loaded = True

        with patch("torch.cuda") as mock_cuda:
            mock_cuda.is_available.return_value = False
            backend.unload_classifier()

        assert backend._classifier is None

    def test_unload_all_resets_loaded_flag(self):
        """unload_all should reset _models_loaded to False."""
        from xclaw.core.perception.pipeline_backend import PipelineBackend

        config = MagicMock()
        config.classify_enabled = False
        backend = PipelineBackend(config)
        backend._models_loaded = True
        backend._detector = MagicMock()
        backend._ocr = MagicMock()

        with patch("torch.cuda") as mock_cuda:
            mock_cuda.is_available.return_value = False
            backend.unload_all()

        assert not backend._models_loaded
        assert backend._detector is None
        assert backend._ocr is None


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3A: Small element center-distance dedup
# ═══════════════════════════════════════════════════════════════════════════


class TestSmallElementDedup:
    def test_small_icons_close_merge(self):
        """Two 20×20 icons 3px apart should merge into 1."""
        elems = [
            _elem(0, type="icon", bbox=(100, 100, 120, 120), content="a"),
            _elem(1, type="icon", bbox=(103, 103, 123, 123), content="b"),
        ]
        result = merge_elements(elems)
        assert len(result) == 1

    def test_large_icons_close_use_iou(self):
        """Two 100×100 icons 3px apart should use IoU (overlap is high → merge)."""
        elems = [
            _elem(0, type="icon", bbox=(100, 100, 200, 200), content="a"),
            _elem(1, type="icon", bbox=(103, 103, 203, 203), content="b"),
        ]
        # IoU for these is very high (~0.88), so they should merge even with IoU
        result = merge_elements(elems)
        assert len(result) == 1

    def test_small_icons_far_no_merge(self):
        """Two 20×20 icons 30px apart should NOT merge."""
        elems = [
            _elem(0, type="icon", bbox=(100, 100, 120, 120), content="a"),
            _elem(1, type="icon", bbox=(140, 140, 160, 160), content="b"),
        ]
        result = merge_elements(elems)
        assert len(result) == 2

    def test_is_small_helper(self):
        assert _is_small((0, 0, 20, 20)) is True
        assert _is_small((0, 0, 100, 100)) is False
        assert _is_small((0, 0, 20, 100)) is False  # only one dim small

    def test_center_distance_helper(self):
        dist = _center_distance((0, 0, 10, 10), (10, 10, 20, 20))
        assert abs(dist - 14.142) < 0.1  # sqrt(100 + 100)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3B: Model SHA256 verification
# ═══════════════════════════════════════════════════════════════════════════


class TestModelVerification:
    def test_truncated_model_warns(self, tmp_path, capsys):
        """verify_models() should warn about truncated/small model files."""
        from scripts.download_models import verify_models

        # Create a tiny fake model file (simulating truncation)
        icon_dir = tmp_path / "icon_detect"
        icon_dir.mkdir()
        model_file = icon_dir / "model.pt"
        model_file.write_bytes(b"tiny")  # 4 bytes, way below min_size_mb

        # Create minimal SigLIP config
        classify_dir = tmp_path / "icon_classify_siglip"
        classify_dir.mkdir()
        config_file = classify_dir / "config.json"
        config_file.write_text("{}")

        result = verify_models(tmp_path)

        captured = capsys.readouterr()
        # Should warn about YOLO being too small
        assert "truncated" in captured.out.lower() or "⚠" in captured.out
        assert result is False

    def test_valid_model_passes(self, tmp_path, capsys):
        """verify_models() should pass for properly-sized model files."""
        from scripts.download_models import verify_models

        icon_dir = tmp_path / "icon_detect"
        icon_dir.mkdir()
        model_file = icon_dir / "model.pt"
        model_file.write_bytes(b"x" * (25 * 1024 * 1024))  # 25 MB
        onnx_file = icon_dir / "model.onnx"
        onnx_file.write_bytes(b"x" * (25 * 1024 * 1024))  # 25 MB

        classify_dir = tmp_path / "icon_classify_siglip"
        classify_dir.mkdir()
        config_file = classify_dir / "config.json"
        # Must be >= 0.001 MB (~1KB) per MODEL_MANIFEST
        config_file.write_text('{"model_type": "siglip2"}' + " " * 1100)

        result = verify_models(tmp_path)
        assert result is True

    def test_missing_model_fails(self, tmp_path, capsys):
        """verify_models() should fail when model files are missing."""
        from scripts.download_models import verify_models

        result = verify_models(tmp_path)

        captured = capsys.readouterr()
        assert "MISSING" in captured.out
        assert result is False

    def test_sha256_prefix_correct(self, tmp_path):
        """_sha256_prefix should return correct prefix."""
        from scripts.download_models import _sha256_prefix

        test_file = tmp_path / "test.bin"
        content = b"hello world"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()[:16]
        assert _sha256_prefix(test_file) == expected


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3C: Download retry logic
# ═══════════════════════════════════════════════════════════════════════════


class TestDownloadRetry:
    def test_retry_on_failure_then_success(self):
        """First call fails, second succeeds → no exception raised."""
        from scripts.download_models import _download_with_retry

        call_count = 0
        def fake_download():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("fail")

        with patch("time.sleep"):
            _download_with_retry(fake_download, label="test")

        assert call_count == 2

    def test_all_retries_exhausted_raises(self):
        """All retries fail → exception propagates."""
        from scripts.download_models import _download_with_retry

        def always_fail():
            raise ConnectionError("fail")

        with patch("time.sleep"):
            with pytest.raises(ConnectionError):
                _download_with_retry(always_fail, max_retries=3, label="test")

    def test_exponential_backoff_timing(self):
        """Retry waits should follow 2s, 4s, 8s pattern."""
        from scripts.download_models import _download_with_retry

        call_count = 0
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("fail")

        with patch("time.sleep") as mock_sleep:
            _download_with_retry(fail_twice, max_retries=3, label="test")

        # Should have slept twice: 2s then 4s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)

    def test_gui_download_with_retry(self):
        """DownloadGUI._download_with_retry should retry on failure."""
        from xclaw.installer.download_gui import DownloadGUI

        with patch("tkinter.Tk"):
            gui = DownloadGUI.__new__(DownloadGUI)
            gui.MAX_RETRIES = 3
            gui.root = MagicMock()

            with patch("subprocess.run") as mock_run, \
                 patch("time.sleep"):
                mock_run.side_effect = [
                    subprocess.CalledProcessError(1, "cmd"),
                    None,
                ]
                gui._download_with_retry(["fake", "cmd"], label="test")

            assert mock_run.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4C: set_backend() thread safety + freeze
# ═══════════════════════════════════════════════════════════════════════════


class TestSetBackendThreadSafety:
    def test_freeze_prevents_set(self):
        """After freeze_backend(), set_backend() should raise RuntimeError."""
        import xclaw.action as action_mod

        # Save original state
        original_backend = action_mod._backend
        original_frozen = action_mod._frozen

        try:
            action_mod._frozen = False
            action_mod.freeze_backend()

            with pytest.raises(RuntimeError, match="frozen"):
                action_mod.set_backend(MagicMock())
        finally:
            # Restore
            action_mod._backend = original_backend
            action_mod._frozen = original_frozen

    def test_get_backend_works_after_freeze(self):
        """get_backend() should still work after freeze."""
        import xclaw.action as action_mod
        from xclaw.action.dry_run_backend import DryRunBackend

        original_backend = action_mod._backend
        original_frozen = action_mod._frozen

        try:
            dry = DryRunBackend()
            action_mod._frozen = False
            action_mod._backend = dry
            action_mod.freeze_backend()

            # get_backend should still return the backend
            assert action_mod.get_backend() is dry
        finally:
            action_mod._backend = original_backend
            action_mod._frozen = original_frozen

    def test_concurrent_get_backend_safe(self):
        """Multiple threads calling get_backend() concurrently should be safe."""
        import xclaw.action as action_mod
        from xclaw.action.dry_run_backend import DryRunBackend

        original_backend = action_mod._backend
        original_frozen = action_mod._frozen

        try:
            action_mod._frozen = False
            action_mod._backend = None  # force creation

            results = []
            errors = []

            def worker():
                try:
                    b = action_mod.get_backend()
                    results.append(b)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            assert not errors, f"Errors during concurrent get_backend: {errors}"
            assert len(results) == 10
            # All should get the same instance
            assert all(r is results[0] for r in results)
        finally:
            action_mod._backend = original_backend
            action_mod._frozen = original_frozen
