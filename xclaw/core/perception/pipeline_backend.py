"""Default perception backend: YOLO (TRT/CUDA) + PaddleOCR + Florence-2 captioner."""

from __future__ import annotations

import time
import logging
from pathlib import Path

import numpy as np

from xclaw.config import MODELS_DIR, WEIGHTS_DIR
from xclaw.platform.gpu import PerceptionConfig
from xclaw.core.perception.types import TextBox

logger = logging.getLogger(__name__)


class PipelineBackend:
    """Default backend — YOLO icon detection + PaddleOCR + Florence-2 captioner."""

    def __init__(self, config: PerceptionConfig):
        self._config = config
        self._models_loaded = False
        self._detector = None  # OmniDetector
        self._ocr = None       # OCREngine
        self._classifier = None  # IconClassifier

    # ── PerceptionBackend protocol ──

    def load_models(self) -> None:
        if self._models_loaded:
            return

        t0 = time.time()
        model_dir = self._find_model_dir()

        # 1. YOLO icon_detect
        from xclaw.core.perception.omniparser import OmniDetector

        onnx_path = model_dir / "icon_detect" / "model.onnx"
        pt_path = model_dir / "icon_detect" / "model.pt"

        if onnx_path.exists():
            # Try TensorRT EP first, fallback to CUDA EP
            if self._config.yolo_trt_enabled:
                try:
                    self._detector = OmniDetector.from_onnx(
                        str(onnx_path),
                        provider="TensorrtExecutionProvider",
                    )
                except Exception as e:
                    logger.info("TensorRT EP unavailable (%s), falling back to %s", e, self._config.yolo_onnx_ep)
                    self._detector = OmniDetector.from_onnx(
                        str(onnx_path),
                        provider=self._config.yolo_onnx_ep,
                    )
            else:
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

        # 2. PaddleOCR
        from xclaw.core.perception.ocr import OCREngine

        self._ocr = OCREngine(
            use_gpu=self._config.ocr_use_gpu,
            det_limit=self._config.ocr_det_limit,
        )

        # 3. Florence-2 icon captioner (from OmniParser V2)
        if self._config.classifier_enabled:
            caption_dir = model_dir / "icon_caption_florence"
            from xclaw.core.perception.icon_classifier import IconClassifier

            self._classifier = IconClassifier(
                model_path=caption_dir,
                device=self._config.classifier_device,
            )
            self._classifier.load()

        self._models_loaded = True
        elapsed = time.time() - t0
        logger.debug("Models loaded in %.1fs\n%s", elapsed, self._config.describe())

    def detect_icons(self, image: np.ndarray, conf: float = 0.3) -> list[dict]:
        self.load_models()
        return self._detector.detect(image, conf)

    def detect_text(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        self.load_models()
        return self._ocr.detect(image, min_confidence)

    def classify_icons(
        self, image: np.ndarray, icon_elements: list[dict]
    ) -> list[str]:
        self.load_models()
        if self._classifier is None:
            return ["unknown" for _ in icon_elements]
        return self._classifier.classify(image, icon_elements)

    @property
    def classifier_enabled(self) -> bool:
        return self._config.classifier_enabled and self._classifier is not None

    # ── internals ──

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
