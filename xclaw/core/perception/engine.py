"""Perception engine — platform-adaptive orchestrator.

Delegates to a :class:`PerceptionBackend` (default: ``PipelineBackend``
which uses YOLO + PaddleOCR + SigLIP 2 classifier).
"""

import base64
import io
import logging
import warnings
from typing import Optional

import numpy as np

from xclaw.config import PERCEPTION_CONFIG
from xclaw.core.perception.backend import PerceptionBackend
from xclaw.core.perception.merger import fuse_results
from xclaw.core.perception.types import TextBox

logger = logging.getLogger(__name__)


class PerceptionEngine:
    """Perception engine — platform-adaptive.

    All model interaction is delegated to a :class:`PerceptionBackend`.
    """

    _instance: Optional["PerceptionEngine"] = None

    @classmethod
    def get_instance(cls) -> "PerceptionEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, backend: Optional[PerceptionBackend] = None):
        self.config = PERCEPTION_CONFIG
        if backend is not None:
            self._backend = backend
        else:
            from xclaw.core.perception.pipeline_backend import PipelineBackend
            self._backend = PipelineBackend(self.config)

    # ── backward-compat shim ──

    def _ensure_models(self):
        """Lazy-load all models (delegates to backend)."""
        self._backend.load_models()

    # ── public API (delegates to backend) ──

    def detect_icons(self, image: np.ndarray, conf: float = 0.3) -> list[dict]:
        return self._backend.detect_icons(image, conf)

    def detect_text(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        return self._backend.detect_text(image, min_confidence)

    def classify_icons(self, image: np.ndarray, icon_elements: list[dict]) -> list[dict]:
        return self._backend.classify_icons(image, icon_elements)

    @property
    def classify_enabled(self) -> bool:
        return self._backend.classify_enabled

    @property
    def classify_conditional(self) -> bool:
        return self._backend.classify_conditional

    # ── perception pipeline ──

    def full_look(
        self,
        region: Optional[list[int]] = None,
        with_image: bool = False,
    ) -> dict:
        """Full perception pipeline (DEPRECATED — use ``run_pipeline()`` instead).

        .. deprecated::
            Use :func:`xclaw.core.pipeline.run_pipeline` which provides
            proper merge dedup and sub-stage timing.
        """
        warnings.warn(
            "PerceptionEngine.full_look() is deprecated, use xclaw.core.pipeline.run_pipeline() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        import time

        self._backend.load_models()

        t_start = time.time()
        degraded: list[str] = []

        # Step 1: Screenshot
        screenshot = self._capture(region=region)
        t_capture = time.time()

        # Step 2: Icon detection
        try:
            icon_boxes = self._backend.detect_icons(screenshot)
        except Exception as e:
            logger.warning("YOLO detection failed, continuing without icons: %s", e)
            icon_boxes = []
            degraded.append("yolo")
        t_yolo = time.time()

        # Step 3: OCR
        try:
            text_boxes = self._backend.detect_text(screenshot)
        except Exception as e:
            logger.warning("OCR failed, continuing without text: %s", e)
            text_boxes = []
            degraded.append("ocr")
        t_ocr = time.time()

        # Step 4: Spatial fusion
        merged, icons_needing_classify = fuse_results(icon_boxes, text_boxes)
        t_merge = time.time()

        # Step 5: Conditional classification
        try:
            if (
                self._backend.classify_enabled
                and icons_needing_classify
            ):
                results = self._backend.classify_icons(screenshot, icons_needing_classify)
                for elem, r in zip(icons_needing_classify, results):
                    elem["content"] = r["label"]
        except Exception as e:
            logger.warning("Classification failed, continuing without labels: %s", e)
            degraded.append("classify")
        t_classify = time.time()

        # Step 6: Assign sequential IDs
        for i, elem in enumerate(merged, start=1):
            elem["id"] = i

        h, w = screenshot.shape[:2]

        result = {
            "status": "ok",
            "element_count": len(merged),
            "elements": merged,
            "resolution": [w, h],
            "timing": {
                "capture_ms": round((t_capture - t_start) * 1000),
                "yolo_ms": round((t_yolo - t_capture) * 1000),
                "ocr_ms": round((t_ocr - t_yolo) * 1000),
                "merge_ms": round((t_merge - t_ocr) * 1000),
                "classify_ms": round((t_classify - t_merge) * 1000),
                "total_ms": round((t_classify - t_start) * 1000),
            },
        }

        if degraded:
            result["degraded"] = degraded

        if with_image:
            result["image_b64"] = self._encode_image(screenshot)

        return result

    def screenshot_only(self, region=None) -> dict:
        """Pure screenshot, no perception."""
        screenshot = self._capture(region=region)
        return {
            "status": "ok",
            "image_b64": self._encode_image(screenshot),
        }

    @staticmethod
    def _capture(region=None) -> np.ndarray:
        """Capture screen as numpy array (RGB)."""
        import mss
        from PIL import Image

        with mss.mss() as sct:
            if region:
                x, y, w, h = region
                monitor = {"left": x, "top": y, "width": w, "height": h}
            else:
                monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        return np.array(img)

    @staticmethod
    def _encode_image(img: np.ndarray) -> str:
        from PIL import Image

        pil_img = Image.fromarray(img)
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
