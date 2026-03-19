"""OmniParser components — YOLO detector, dual backend."""

import numpy as np
from pathlib import Path


def _iou(a, b):
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter + 1e-6)


class OmniDetector:
    """YOLO icon_detect — dual backend.

    Prefers ONNX Runtime (lightweight), falls back to ultralytics.
    """

    def __init__(self, session=None, yolo_model=None, device="cpu"):
        self._onnx_session = session
        self._yolo_model = yolo_model
        self._device = device

    @classmethod
    def from_onnx(cls, onnx_path: str, provider: str = "CPUExecutionProvider"):
        """Load via ONNX Runtime (recommended)."""
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        providers = []
        if provider == "CUDAExecutionProvider":
            providers.append(("CUDAExecutionProvider", {
                "device_id": 0,
                "arena_extend_strategy": "kSameAsRequested",
            }))
        elif provider == "CoreMLExecutionProvider":
            providers.append("CoreMLExecutionProvider")
        providers.append("CPUExecutionProvider")

        session = ort.InferenceSession(onnx_path, opts, providers=providers)
        return cls(session=session)

    @classmethod
    def from_ultralytics(cls, pt_path: str, device: str = "cpu"):
        """Load via ultralytics (fallback)."""
        from ultralytics import YOLO

        model = YOLO(pt_path)
        return cls(yolo_model=model, device=device)

    def detect(self, image: np.ndarray, conf: float = 0.3) -> list[dict]:
        if self._onnx_session:
            return self._detect_onnx(image, conf)
        else:
            return self._detect_ultralytics(image, conf)

    def _detect_onnx(self, image: np.ndarray, conf: float) -> list[dict]:
        import cv2

        h_orig, w_orig = image.shape[:2]

        img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (640, 640))
        blob = (img.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis]

        input_name = self._onnx_session.get_inputs()[0].name
        outputs = self._onnx_session.run(None, {input_name: blob})

        return self._postprocess(outputs, w_orig, h_orig, conf)

    def _detect_ultralytics(self, image: np.ndarray, conf: float) -> list[dict]:
        results = self._yolo_model.predict(
            image, conf=conf, device=self._device, verbose=False
        )
        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append({
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                    "confidence": round(float(box.conf[0]), 3),
                    "class_id": int(box.cls[0]),
                })
        return detections

    def _postprocess(self, outputs, w_orig, h_orig, conf_threshold):
        preds = outputs[0][0].T  # (8400, 4+C)
        boxes_xywh = preds[:, :4]
        scores = preds[:, 4:].max(axis=1)
        mask = scores > conf_threshold

        if not mask.any():
            return []

        boxes_xywh = boxes_xywh[mask]
        scores = scores[mask]

        sx, sy = w_orig / 640, h_orig / 640
        results = []
        for (cx, cy, w, h), score in zip(boxes_xywh, scores):
            results.append({
                "bbox": (
                    int((cx - w / 2) * sx), int((cy - h / 2) * sy),
                    int((cx + w / 2) * sx), int((cy + h / 2) * sy),
                ),
                "confidence": round(float(score), 3),
            })

        # NMS
        results.sort(key=lambda d: d["confidence"], reverse=True)
        keep = []
        for det in results:
            if all(_iou(det["bbox"], k["bbox"]) < 0.5 for k in keep):
                keep.append(det)
        return keep
