"""Default perception backend: YOLO + RapidOCR + SigLIP 2 classifier."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np

import logging

from xclaw.config import MODELS_DIR, WEIGHTS_DIR
from xclaw.platform.gpu import PerceptionConfig
from xclaw.core.perception.types import TextBox

logger = logging.getLogger(__name__)


class PipelineBackend:
    """Default backend — YOLO icon detection + RapidOCR + SigLIP 2 classifier."""

    def __init__(self, config: PerceptionConfig):
        self._config = config
        self._models_loaded = False
        self._detector = None  # OmniDetector
        self._ocr = None       # OCREngine
        self._classifier = None  # SigLIPClassifier
        self.load_timing: dict[str, int] = {}  # per-model load times (ms)

    # ── PerceptionBackend protocol ──

    def load_models(self) -> None:
        if self._models_loaded:
            return

        t_total = time.perf_counter_ns()
        model_dir = self._find_model_dir()

        # 1. YOLO icon_detect
        t = time.perf_counter_ns()
        from xclaw.core.perception.omniparser import OmniDetector

        onnx_path = model_dir / "icon_detect" / "model.onnx"
        pt_path = model_dir / "icon_detect" / "model.pt"

        if onnx_path.exists():
            self._detector = OmniDetector.from_onnx(
                str(onnx_path),
                provider=self._config.yolo_onnx_ep,
            )
        elif pt_path.exists():
            self._detector = OmniDetector.from_ultralytics(
                str(pt_path),
                device=self._config.yolo_device,
            )
        else:
            raise FileNotFoundError(
                f"No YOLO model found at {model_dir / 'icon_detect'}. "
                "Run: uv run python scripts/download_models.py"
            )
        self.load_timing["yolo_ms"] = (time.perf_counter_ns() - t) // 1_000_000

        # 2. RapidOCR
        t = time.perf_counter_ns()
        from xclaw.core.perception.ocr import OCREngine

        self._ocr = OCREngine(
            use_gpu=self._config.ocr_use_gpu,
            det_limit=self._config.ocr_det_limit,
        )
        self.load_timing["ocr_ms"] = (time.perf_counter_ns() - t) // 1_000_000

        # 3. SigLIP 2 classifier (conditional)
        t = time.perf_counter_ns()
        if self._config.classify_enabled:
            classify_dir = model_dir / "icon_classify_siglip"
            if classify_dir.exists():
                try:
                    from xclaw.core.perception.siglip_classifier import SigLIPClassifier

                    import torch

                    dtype = (
                        torch.float16
                        if self._config.classify_dtype == "float16"
                        else torch.float32
                    )
                    self._classifier = SigLIPClassifier(
                        model_dir=classify_dir,
                        device=self._config.classify_device,
                        dtype=dtype,
                    )
                except Exception as e:
                    logger.warning(
                        "SigLIP classifier load failed, continuing without classification: %s", e
                    )
                    self._classifier = None
        self.load_timing["siglip_ms"] = (time.perf_counter_ns() - t) // 1_000_000

        self._models_loaded = True
        self.load_timing["total_ms"] = (time.perf_counter_ns() - t_total) // 1_000_000
        logger.debug("Models loaded in %dms (yolo=%dms, ocr=%dms, siglip=%dms)\n%s",
                      self.load_timing["total_ms"],
                      self.load_timing["yolo_ms"],
                      self.load_timing["ocr_ms"],
                      self.load_timing["siglip_ms"],
                      self._config.describe())

    def detect_icons(self, image: np.ndarray, conf: float = 0.3) -> list[dict]:
        self.load_models()
        return self._detector.detect(image, conf)

    def detect_text(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        self.load_models()
        return self._ocr.detect(image, min_confidence)

    def classify_icons(
        self, image: np.ndarray, icon_elements: list[dict]
    ) -> list[dict]:
        self.load_models()
        if self._classifier is None:
            return [{"label": "", "confidence": 0.0} for _ in icon_elements]
        return self._classifier.batch_classify(image, icon_elements)

    @property
    def classify_enabled(self) -> bool:
        return self._config.classify_enabled and self._classifier is not None

    @property
    def classify_conditional(self) -> bool:
        return self._config.classify_conditional

    # ── internals ──

    def unload_classifier(self) -> None:
        """Release SigLIP classifier from memory."""
        if self._classifier is not None:
            del self._classifier
            self._classifier = None
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()

    def unload_all(self) -> None:
        """Release all models from memory."""
        self.unload_classifier()
        self._detector = None
        self._ocr = None
        self._models_loaded = False
        import gc
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()

    @staticmethod
    def _find_model_dir() -> Path:
        candidates = [
            MODELS_DIR,                                      # models/ (new)
            WEIGHTS_DIR,                                     # weights/ (legacy)
            Path(__file__).parents[2] / "models",            # relative
            Path.home() / ".xclaw" / "models",               # user install
        ]
        for p in candidates:
            if (p / "icon_detect").exists():
                return p
        raise FileNotFoundError(
            "Model directory not found. Run: uv run python scripts/download_models.py"
        )
