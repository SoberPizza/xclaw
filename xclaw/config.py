"""Centralized configuration for X-Claw — Windows CUDA only."""

from pathlib import Path
import os

# ── 静默第三方库噪声（须在任何第三方 import 之前） ──
os.environ.setdefault("YOLO_VERBOSE", "False")

# 项目根目录
PROJECT_ROOT = Path(os.environ["XCLAW_HOME"]) if "XCLAW_HOME" in os.environ else Path(__file__).resolve().parent.parent


def _resolve_data_dir() -> Path:
    """User-writable data directory (screenshots, logs, state, models)."""
    if "XCLAW_DATA" in os.environ:
        return Path(os.environ["XCLAW_DATA"])
    # 开发模式：pyproject.toml 存在 → 就用 PROJECT_ROOT
    if (PROJECT_ROOT / "pyproject.toml").exists():
        return PROJECT_ROOT
    # 安装模式 (Windows)
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "X-Claw"


DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 路径 ──
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
LOGS_DIR = DATA_DIR / "logs"
WEIGHTS_DIR = PROJECT_ROOT / "weights"

# ── 行为人性化 ──
HUMANIZE = os.environ.get("XCLAW_HUMANIZE", "0") == "1"
BEZIER_DURATION_RANGE = (0.3, 0.8)
BEZIER_STEPS = 30
TYPE_DELAY_RANGE = (0.05, 0.15)

# ── L1: Perception / Merger ──
MERGER_IOU_THRESHOLD = 0.5
MERGER_SMALL_ELEMENT_SIZE = 32               # 双维低于此值的元素视为"小元素"
MERGER_SMALL_ELEMENT_CENTER_DIST = 15        # 小元素去重：中心点距离阈值（px）

# ── Pipeline Cache ──
CACHE_MAX_SIZE = 8

# ── Artifact retention ──
MAX_SCREENSHOTS = 100
MAX_LOGS = 100

# ── TensorRT ──
YOLO_TRT_ENABLED = os.environ.get("XCLAW_TRT", "1") == "1"

# ── 平台适配 ──
from xclaw.platform import PLATFORM, PERCEPTION_CONFIG  # noqa: E402

# 模型目录（搜索顺序：PROJECT_ROOT/models → weights → DATA_DIR/models → ~/.xclaw/models）
def _resolve_models_dir() -> Path:
    for candidate in [
        PROJECT_ROOT / "models",
        WEIGHTS_DIR,
        DATA_DIR / "models",
        Path.home() / ".xclaw" / "models",
    ]:
        if (candidate / "icon_detect").exists():
            return candidate
    # 默认返回首选路径（模型可能尚未下载）
    return PROJECT_ROOT / "models" if (PROJECT_ROOT / "pyproject.toml").exists() else DATA_DIR / "models"


MODELS_DIR = _resolve_models_dir()
