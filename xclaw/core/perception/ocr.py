"""PaddleOCR engine — CPU on all platforms."""

import numpy as np

from xclaw.core.perception.types import TextBox


class OCREngine:
    """PaddleOCR v4 mobile — Chinese/English bilingual, CPU on all platforms.

    OCR runs ~180ms on CPU which is not a bottleneck. Using CPU-only
    paddlepaddle avoids nvidia-cudnn version conflicts with torch.
    """

    def __init__(self, use_gpu: bool = False, det_limit: int = 960):
        import logging as _logging
        import os
        import sys

        # Disable oneDNN — PaddlePaddle 3.x CPU has a PIR+oneDNN bug on Windows
        os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

        # Pre-configure paddlex logger before import to block colorlog handler.
        # CLI path sets this in _silence_for_cli(); this covers daemon_server path.
        _pdx = _logging.getLogger("paddlex")
        if not _pdx.handlers:
            _pdx.addHandler(_logging.NullHandler())
            _pdx.setLevel(_logging.CRITICAL)
            _pdx.propagate = False

        # Suppress C++ stderr noise from PaddlePaddle DLL search on Windows
        # ("消息: 所提供的模式无法找到文件。") during import paddle.
        saved_fd = None
        if sys.platform == "win32":
            try:
                stderr_fd = sys.stderr.fileno()
                saved_fd = os.dup(stderr_fd)
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, stderr_fd)
                os.close(devnull)
            except OSError:
                saved_fd = None

        try:
            from paddleocr import PaddleOCR

            self.engine = PaddleOCR(
                use_textline_orientation=True,
                lang="ch",
                text_det_limit_side_len=det_limit,
                device="cpu" if not use_gpu else "gpu",
            )
        finally:
            if saved_fd is not None:
                os.dup2(saved_fd, sys.stderr.fileno())
                os.close(saved_fd)

    def detect(self, image: np.ndarray, min_confidence: float = 0.6) -> list[TextBox]:
        results = list(self.engine.predict(image))
        if not results:
            return []

        r = results[0]
        polys = r["dt_polys"]
        texts = r["rec_texts"]
        scores = r["rec_scores"]

        boxes = []
        for polygon, text, confidence in zip(polys, texts, scores):
            if confidence < min_confidence:
                continue
            poly_list = polygon.tolist() if hasattr(polygon, "tolist") else polygon
            xs = [p[0] for p in poly_list]
            ys = [p[1] for p in poly_list]
            boxes.append(TextBox(
                bbox=(int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
                text=text.strip(),
                confidence=round(confidence, 3),
                polygon=poly_list,
            ))
        return boxes
