"""Platform detection, GPU configuration, and permissions."""

from xclaw.platform.detect import detect_platform, PlatformInfo
from xclaw.platform.gpu import build_perception_config, PerceptionConfig

PLATFORM: PlatformInfo = detect_platform()
PERCEPTION_CONFIG: PerceptionConfig = build_perception_config(PLATFORM)

__all__ = [
    "PLATFORM",
    "PERCEPTION_CONFIG",
    "PlatformInfo",
    "PerceptionConfig",
    "detect_platform",
    "build_perception_config",
]
