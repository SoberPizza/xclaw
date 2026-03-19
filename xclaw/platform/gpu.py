"""GPU / device configuration for the perception engine."""

from dataclasses import dataclass

from xclaw.platform.detect import detect_platform


@dataclass
class PerceptionConfig:
    """Hardware configuration for the perception engine."""
    yolo_device: str            # "cuda" | "mps" | "cpu"
    yolo_onnx_ep: str           # ONNX Execution Provider
    caption_device: str         # "cuda" | "cpu" (macOS cannot use mps)
    caption_dtype: str          # "float16" | "float32"
    caption_enabled: bool
    caption_conditional: bool   # only trigger for icons without text
    ocr_use_gpu: bool
    ocr_det_limit: int          # max input image side length

    def describe(self) -> str:
        lines = [
            f"YOLO: {self.yolo_device} ({self.yolo_onnx_ep})",
            f"Caption: {self.caption_device} {self.caption_dtype}",
            f"  enabled={self.caption_enabled}, conditional={self.caption_conditional}",
            f"OCR: {'GPU' if self.ocr_use_gpu else 'CPU'}, det_limit={self.ocr_det_limit}",
        ]
        return "\n".join(lines)


def build_perception_config() -> PerceptionConfig:
    """Build optimal perception config for the current platform."""
    plat = detect_platform()

    if not plat.supported:
        raise SystemError(plat.support_reason)

    # ── Windows + CUDA ──
    if plat.system == "Windows" and plat.gpu_backend == "cuda":
        return PerceptionConfig(
            yolo_device="cuda",
            yolo_onnx_ep="CUDAExecutionProvider",
            caption_device="cuda",
            caption_dtype="float16",
            caption_enabled=True,
            caption_conditional=True,
            ocr_use_gpu=True,
            ocr_det_limit=960,
        )

    # ── macOS Apple Silicon ──
    if plat.system == "Darwin" and plat.is_apple_silicon:
        return PerceptionConfig(
            yolo_device="mps",
            yolo_onnx_ep="CoreMLExecutionProvider",
            caption_device="cpu",            # MPS gather bug, force CPU
            caption_dtype="float32",         # CPU does not support FP16
            caption_enabled=True,
            caption_conditional=True,        # conditional invocation saves time
            ocr_use_gpu=False,               # PaddlePaddle macOS has no GPU
            ocr_det_limit=960,
        )

    # ── Fallback: CPU ──
    return PerceptionConfig(
        yolo_device="cpu",
        yolo_onnx_ep="CPUExecutionProvider",
        caption_device="cpu",
        caption_dtype="float32",
        caption_enabled=True,
        caption_conditional=True,
        ocr_use_gpu=False,
        ocr_det_limit=640,
    )
