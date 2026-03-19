"""Default perception backend: YOLO + PaddleOCR + MiniCPM-V 2.0."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from xclaw.config import MODELS_DIR, WEIGHTS_DIR
from xclaw.platform.gpu import PerceptionConfig
from xclaw.core.perception.types import TextBox


class PipelineBackend:
    """Default backend — YOLO icon detection + PaddleOCR + MiniCPM-V caption."""

    def __init__(self, config: PerceptionConfig):
        self._config = config
        self._models_loaded = False
        self._detector = None  # OmniDetector
        self._ocr = None       # OCREngine
        self._caption = None   # MiniCPMCaption

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

        # 3. MiniCPM-V (conditional)
        if self._config.caption_enabled:
            caption_dir = model_dir / "icon_caption_minicpm"
            if caption_dir.exists():
                from xclaw.core.perception.minicpm_caption import MiniCPMCaption

                dtype = (
                    torch.float16
                    if self._config.caption_dtype == "float16"
                    else torch.float32
                )
                self._caption = MiniCPMCaption(
                    model_dir=caption_dir,
                    device=self._config.caption_device,
                    dtype=dtype,
                )

        self._models_loaded = True
        elapsed = time.time() - t0
        print(f"[backend] Models loaded in {elapsed:.1f}s\n{self._config.describe()}")

    def detect_icons(self, image: np.ndarray, conf: float = 0.3) -> list[dict]:
        self.load_models()
        return self._detector.detect(image, conf)

    def detect_text(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        self.load_models()
        return self._ocr.detect(image, min_confidence)

    def caption_icons(
        self, image: np.ndarray, icon_elements: list[dict]
    ) -> list[str]:
        self.load_models()
        if self._caption is None:
            return ["" for _ in icon_elements]
        return self._caption.batch_caption(image, icon_elements)

    @property
    def caption_enabled(self) -> bool:
        return self._config.caption_enabled and self._caption is not None

    @property
    def caption_conditional(self) -> bool:
        return self._config.caption_conditional

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
