"""Platform detection tests — mock-based, no GPU required."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from xclaw.platform.detect import PlatformInfo, detect_platform, _get_memory_gb, _detect_gpu_backend
from xclaw.platform.gpu import PerceptionConfig, build_perception_config


# ---------------------------------------------------------------------------
# PlatformInfo dataclass
# ---------------------------------------------------------------------------


class TestPlatformInfo:
    def test_macos_apple_silicon_supported(self):
        info = PlatformInfo(
            system="Darwin", arch="arm64",
            is_apple_silicon=True, memory_gb=16, gpu_backend="mps",
        )
        assert info.supported is True
        assert info.support_reason == "OK"

    def test_macos_insufficient_memory(self):
        info = PlatformInfo(
            system="Darwin", arch="arm64",
            is_apple_silicon=True, memory_gb=8, gpu_backend="mps",
        )
        assert info.supported is False
        assert "16GB" in info.support_reason

    def test_windows_always_supported(self):
        info = PlatformInfo(
            system="Windows", arch="AMD64",
            is_apple_silicon=False, memory_gb=8, gpu_backend="cuda",
        )
        assert info.supported is True

    def test_frozen(self):
        info = PlatformInfo(
            system="Darwin", arch="arm64",
            is_apple_silicon=True, memory_gb=16, gpu_backend="mps",
        )
        with pytest.raises(AttributeError):
            info.system = "Windows"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# detect_platform()
# ---------------------------------------------------------------------------


class TestDetectPlatform:
    @patch("xclaw.platform.detect.platform")
    @patch("xclaw.platform.detect._get_memory_gb", return_value=16)
    @patch("xclaw.platform.detect._detect_gpu_backend", return_value="mps")
    def test_darwin_arm64(self, mock_gpu, mock_mem, mock_plat):
        mock_plat.system.return_value = "Darwin"
        mock_plat.machine.return_value = "arm64"

        info = detect_platform()
        assert info.system == "Darwin"
        assert info.arch == "arm64"
        assert info.is_apple_silicon is True
        assert info.memory_gb == 16
        assert info.gpu_backend == "mps"

    @patch("xclaw.platform.detect.platform")
    @patch("xclaw.platform.detect._get_memory_gb", return_value=32)
    @patch("xclaw.platform.detect._detect_gpu_backend", return_value="cuda")
    def test_windows_amd64(self, mock_gpu, mock_mem, mock_plat):
        mock_plat.system.return_value = "Windows"
        mock_plat.machine.return_value = "AMD64"

        info = detect_platform()
        assert info.system == "Windows"
        assert info.arch == "AMD64"
        assert info.is_apple_silicon is False
        assert info.gpu_backend == "cuda"

    @patch("xclaw.platform.detect.platform")
    @patch("xclaw.platform.detect._get_memory_gb", return_value=64)
    @patch("xclaw.platform.detect._detect_gpu_backend", return_value="cpu")
    def test_linux_x86(self, mock_gpu, mock_mem, mock_plat):
        mock_plat.system.return_value = "Linux"
        mock_plat.machine.return_value = "x86_64"

        info = detect_platform()
        assert info.system == "Linux"
        assert info.is_apple_silicon is False
        assert info.gpu_backend == "cpu"


# ---------------------------------------------------------------------------
# _get_memory_gb()
# ---------------------------------------------------------------------------


class TestGetMemoryGB:
    @patch("xclaw.platform.detect.platform")
    @patch("xclaw.platform.detect.subprocess")
    def test_darwin_sysctl(self, mock_subprocess, mock_plat):
        mock_plat.system.return_value = "Darwin"
        mock_subprocess.check_output.return_value = b"17179869184\n"  # 16 GB

        result = _get_memory_gb()
        assert result == 16

    @patch("xclaw.platform.detect.platform")
    def test_fallback_on_error(self, mock_plat):
        mock_plat.system.return_value = "UnknownOS"

        result = _get_memory_gb()
        assert result == 16  # conservative default


# ---------------------------------------------------------------------------
# _detect_gpu_backend()
# ---------------------------------------------------------------------------


class TestDetectGPUBackend:
    def test_windows_with_cuda(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = _detect_gpu_backend("Windows", False)
        assert result == "cuda"

    def test_windows_no_cuda(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = _detect_gpu_backend("Windows", False)
        assert result == "cpu"

    def test_darwin_apple_silicon_mps(self):
        mock_torch = MagicMock()
        mock_torch.backends.mps.is_available.return_value = True

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = _detect_gpu_backend("Darwin", True)
        assert result == "mps"

    def test_darwin_intel(self):
        result = _detect_gpu_backend("Darwin", False)
        assert result == "cpu"

    def test_linux_cpu_fallback(self):
        result = _detect_gpu_backend("Linux", False)
        assert result == "cpu"


# ---------------------------------------------------------------------------
# PerceptionConfig
# ---------------------------------------------------------------------------


class TestPerceptionConfig:
    def test_describe_output(self):
        cfg = PerceptionConfig(
            yolo_device="mps",
            yolo_onnx_ep="CoreMLExecutionProvider",
            caption_device="cpu",
            caption_dtype="float32",
            caption_enabled=True,
            caption_conditional=True,
            ocr_use_gpu=False,
            ocr_det_limit=960,
        )
        desc = cfg.describe()
        assert "YOLO" in desc
        assert "Caption" in desc
        assert "OCR" in desc
        assert "CoreMLExecutionProvider" in desc


# ---------------------------------------------------------------------------
# build_perception_config()
# ---------------------------------------------------------------------------


class TestBuildPerceptionConfig:
    @patch("xclaw.platform.gpu.detect_platform")
    def test_windows_cuda(self, mock_detect):
        mock_detect.return_value = PlatformInfo(
            system="Windows", arch="AMD64",
            is_apple_silicon=False, memory_gb=32, gpu_backend="cuda",
        )
        cfg = build_perception_config()
        assert cfg.yolo_device == "cuda"
        assert cfg.yolo_onnx_ep == "CUDAExecutionProvider"
        assert cfg.caption_device == "cuda"
        assert cfg.caption_dtype == "float16"
        assert cfg.ocr_use_gpu is True

    @patch("xclaw.platform.gpu.detect_platform")
    def test_macos_apple_silicon(self, mock_detect):
        mock_detect.return_value = PlatformInfo(
            system="Darwin", arch="arm64",
            is_apple_silicon=True, memory_gb=16, gpu_backend="mps",
        )
        cfg = build_perception_config()
        assert cfg.yolo_device == "mps"
        assert cfg.yolo_onnx_ep == "CoreMLExecutionProvider"
        assert cfg.caption_device == "cpu"
        assert cfg.caption_dtype == "float32"
        assert cfg.ocr_use_gpu is False

    @patch("xclaw.platform.gpu.detect_platform")
    def test_cpu_fallback(self, mock_detect):
        mock_detect.return_value = PlatformInfo(
            system="Linux", arch="x86_64",
            is_apple_silicon=False, memory_gb=32, gpu_backend="cpu",
        )
        cfg = build_perception_config()
        assert cfg.yolo_device == "cpu"
        assert cfg.yolo_onnx_ep == "CPUExecutionProvider"
        assert cfg.caption_device == "cpu"
        assert cfg.caption_dtype == "float32"
        assert cfg.ocr_det_limit == 640

    @patch("xclaw.platform.gpu.detect_platform")
    def test_unsupported_raises(self, mock_detect):
        mock_detect.return_value = PlatformInfo(
            system="Darwin", arch="arm64",
            is_apple_silicon=True, memory_gb=8, gpu_backend="mps",
        )
        with pytest.raises(SystemError, match="16GB"):
            build_perception_config()
