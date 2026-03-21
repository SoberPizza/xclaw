"""RapidOCR engine — ONNX Runtime, CPU on all platforms.

Replaces PaddleOCR/PaddleX with rapidocr-onnxruntime for ~7x faster inference.
Uses the same PaddleOCR v4 ONNX models but runs on ONNX Runtime directly.
"""

import numpy as np

from xclaw.core.perception.types import TextBox


class OCREngine:
    """RapidOCR — Chinese/English bilingual, ONNX Runtime CPU."""

    def __init__(
        self,
        use_gpu: bool = False,
        det_limit: int = 960,
        det_model: str | None = None,
        rec_model: str | None = None,
    ):
        from rapidocr_onnxruntime import RapidOCR

        kwargs: dict = {
            "intra_op_num_threads": 4,
            "inter_op_num_threads": 4,
            "max_side_len": det_limit,
            "text_score": 0.5,
            "use_cls": False,
        }

        # Custom model paths (if provided)
        if det_model is not None:
            kwargs["det_model_path"] = det_model
        if rec_model is not None:
            kwargs["rec_model_path"] = rec_model

        self.engine = RapidOCR(**kwargs)

    def detect(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        result, _elapse = self.engine(image)
        if not result:
            return []

        boxes = []
        for item in result:
            polygon, text, confidence = item[0], item[1], item[2]
            if confidence < min_confidence:
                continue
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            boxes.append(TextBox(
                bbox=(int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
                text=text.strip(),
                confidence=round(confidence, 3),
                polygon=polygon,
            ))
        return boxes
