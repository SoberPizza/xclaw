"""GPU / device configuration for the perception engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclaw.platform.detect import PlatformInfo


@dataclass
class PerceptionConfig:
    """Hardware configuration for the perception engine."""
    yolo_device: str            # "cuda" | "mps" | "cpu"
    yolo_onnx_ep: str           # ONNX Execution Provider
    classify_device: str        # "cuda" | "mps" | "cpu"
    classify_dtype: str         # "float16" | "float32"
    classify_enabled: bool
    classify_conditional: bool  # only trigger for icons without text
    ocr_use_gpu: bool
    ocr_det_limit: int          # max input image side length

    def describe(self) -> str:
        lines = [
            f"YOLO: {self.yolo_device} ({self.yolo_onnx_ep})",
            f"Classify: {self.classify_device} {self.classify_dtype}",
            f"  enabled={self.classify_enabled}, conditional={self.classify_conditional}",
            f"OCR: {'GPU' if self.ocr_use_gpu else 'CPU'}, det_limit={self.ocr_det_limit}",
        ]
        return "\n".join(lines)


def build_perception_config(platform_info: PlatformInfo | None = None) -> PerceptionConfig:
    """Build optimal perception config for the current platform."""
    if platform_info is None:
        from xclaw.platform.detect import detect_platform
        platform_info = detect_platform()
    plat = platform_info

    if not plat.supported:
        raise SystemError(plat.support_reason)

    # ── Windows + CUDA ──
    if plat.system == "Windows" and plat.gpu_backend == "cuda":
        return PerceptionConfig(
            yolo_device="cuda",
            yolo_onnx_ep="CUDAExecutionProvider",
            classify_device="cuda",
            classify_dtype="float16",
            classify_enabled=True,
            classify_conditional=True,
            ocr_use_gpu=False,               # CPU — avoids nvidia-cudnn version conflicts
            ocr_det_limit=960,
        )

    # ── macOS Apple Silicon ──
    if plat.system == "Darwin" and plat.is_apple_silicon:
        return PerceptionConfig(
            yolo_device="mps",
            yolo_onnx_ep="CoreMLExecutionProvider",
            classify_device="mps",           # SigLIP works on MPS
            classify_dtype="float32",
            classify_enabled=True,
            classify_conditional=True,
            ocr_use_gpu=False,               # PaddlePaddle macOS has no GPU
            ocr_det_limit=960,
        )

    # ── Fallback: CPU ──
    return PerceptionConfig(
        yolo_device="cpu",
        yolo_onnx_ep="CPUExecutionProvider",
        classify_device="cpu",
        classify_dtype="float32",
        classify_enabled=True,
        classify_conditional=True,
        ocr_use_gpu=False,
        ocr_det_limit=640,
    )
