"""Centralized configuration for X-Claw."""

from pathlib import Path
import os

# ── 静默第三方库噪声（须在任何第三方 import 之前） ──
os.environ.setdefault("YOLO_VERBOSE", "False")

# 项目根目录
PROJECT_ROOT = Path(os.environ["XCLAW_HOME"]) if "XCLAW_HOME" in os.environ else Path(__file__).resolve().parent.parent

# ── 路径 ──
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
LOGS_DIR = PROJECT_ROOT / "logs"
WEIGHTS_DIR = PROJECT_ROOT / "weights"

# ── OmniParser ──
OMNIPARSER_DIR = PROJECT_ROOT / "OmniParser"
OMNIPARSER_CONFIG = {
    "som_model_path": str(WEIGHTS_DIR / "icon_detect" / "model.pt"),
    "caption_model_name": "florence2",
    "caption_model_path": str(WEIGHTS_DIR / "icon_caption_florence"),
    "BOX_TRESHOLD": 0.01,
}

# ── 行为人性化 ──
HUMANIZE = os.environ.get("XCLAW_HUMANIZE", "0") == "1"
BEZIER_DURATION_RANGE = (0.3, 0.8)
BEZIER_STEPS = 30
TYPE_DELAY_RANGE = (0.05, 0.15)

# ── Chrome DevTools Protocol ──
CDP_HOST = os.environ.get("XCLAW_CDP_HOST", "127.0.0.1")
CDP_PORT = int(os.environ.get("XCLAW_CDP_PORT", "9222"))

# ── L1: Perception / Merger ──
MERGER_IOU_THRESHOLD = 0.5

# ── L2: Spatial Aggregation ──
ROW_Y_TOLERANCE = 8

# ── Pipeline Cache ──
CACHE_MAX_SIZE = 8

# ── Context: Smart Perception ──
CONTEXT_STATE_PATH = SCREENSHOTS_DIR / ".context_state.json"
CONTEXT_CACHE_TTL = 15.0                    # 缓存过期秒数
CONTEXT_MAX_CONSECUTIVE_CHEAP = 4           # 连续 L0/L1 上限
CONTEXT_DIFF_THRESHOLD_UNCHANGED = 0.01     # 低于此 = 无变化
CONTEXT_DIFF_THRESHOLD_MINOR = 0.15         # 低于此 = 小变化 → L2
CONTEXT_CRITICAL_KEYS = {"enter", "f5"}     # 强制全量管线的按键
CONTEXT_PIXEL_DIFF_THRESHOLD = 30           # peek 灰度差阈值
CONTEXT_CONTOUR_MIN_AREA = 50               # peek 轮廓最小面积（过滤噪声）
CONTEXT_CONTOUR_MERGE_DISTANCE = 20         # peek 轮廓合并距离
CONTEXT_GLANCE_FALLBACK_RATIO = 0.6         # glance 变化面积占比超此值则回退全量管线
CONTEXT_OVERLAP_DISCARD_THRESHOLD = 0.5     # glance 缓存元素重叠比超此值则丢弃
CONTEXT_CONFIDENCE_L0 = 0.8                 # predict 置信度阈值: L0
CONTEXT_CONFIDENCE_L1 = 0.5                 # predict 置信度阈值: L1
CONTEXT_CONFIDENCE_L2 = 0.3                 # predict 置信度阈值: L2
