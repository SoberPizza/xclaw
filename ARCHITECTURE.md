# X-Claw 技术栈与架构分析

## 📋 项目概述

**X-Claw** 是一套基于 OmniParser V2 的**视觉代理框架**，能够让 LLM 通过 CLI 命令控制 Windows 桌面上的 Chrome 浏览器，完成 X/Twitter 等网站的自动化交互。

整个系统采用**分层感知架构**（L0→L1→L2→L3），在保证准确度的同时优化性能。核心架构设计理念："渐进式感知"——从缓存预测开始，根据实时变化智能升级感知深度。

---

## 🛠️ 技术栈速览

### 核心技术栈

| 层级             | 技术          | 说明                                    |
| ---------------- | ------------- | --------------------------------------- |
| **运行时**       | Python 3.12   | 通过 `.python-version` 锁定版本         |
| **包管理**       | uv            | 私有 PyTorch 源（CUDA 12.1）+ 公共 PyPI |
| **深度学习框架** | PyTorch 2.5+  | GPU 推理（CUDA 12.1）                   |
| **视觉识别**     | OmniParser V2 | 自定义修复：PaddleOCR 参数补丁          |

### 关键依赖

**视觉感知层**（需 GPU）：

- `ultralytics>=8.0.0` — YOLO 目标检测
- `transformers>=4.40.0,<4.46.0` — Florence2 视觉语言模型（版本锁定！）
- `timm>=1.0.0` — 视觉骨干网络（ResNet、ViT 等）
- `einops>=0.8.0` — 张量操作
- `supervision>=0.25.0` — 目标检测后处理
- `accelerate>=0.30.0` — 多 GPU 加速

**OCR 层**（双引擎）：

- `easyocr>=1.7.0` — EasyOCR
- `paddlepaddle>=2.6.0` + `paddleocr>=2.7.0` — PaddleOCR

**桌面控制**：

- `pyautogui>=0.9.54` — 鼠标键盘模拟
- `mss>=9.0.0` — 超快速截图（使用原生 Windows API）

**其他工具**：

- `click>=8.0.0` — CLI 框架
- `rich>=13.0.0` — 终端彩色输出
- `huggingface-hub[cli]>=0.25.0` — 模型权重下载
- `Pillow>=10.0.0` — 图像处理
- `opencv-python-headless>=4.8.0` — 计算机视觉（无 GUI）
- `openai>=1.3.0` — API 调用（备用）
- `safetensors>=0.4.0` — 高效的 Transformer 权重加载

---

## 📁 核心模块架构

### 1. 感知管道（Perception Pipeline - L1）

```
截屏 (screen.py)
    ↓ mss 超快速截图
OmniParser 解析 (perception/omniparser.py)
    ├── 目标检测 (icon_detect/model.pt) — YOLO
    ├── 图标标题识别 (Florence2) — 视觉语言模型
    └── OCR 融合 (EasyOCR + PaddleOCR) — 文本识别
    ↓
元素融合 (perception/merger.py)
    └── IoU 去重合并 (threshold: 0.5)
    ↓
RawElement 列表
    ├── 位置 (bbox)
    ├── 类别 (text, button, label, etc.)
    └── 文本内容 + 置信度
```

**关键文件**：

- `xclaw/core/perception/omniparser.py` — OmniParser 封装 + PaddleOCR 补丁
- `xclaw/core/perception/merger.py` — 元素去重融合
- `xclaw/core/perception/ocr.py` — OCR 双引擎管理

**性能指标**：

- 单次识别延迟：~2-2.5 秒（GPU）
- 元素平均数：150-300 个/页

---

### 2. 空间聚合层（L2 Spatial）

```
RawElements (无序)
    ↓
行检测 (spatial/block_segmenter.py)
    └── 按 Y 坐标聚类，容差 8px
    ↓ Row 列表
列检测 (spatial/column_detector.py)
    └── 按 X 坐标分组，最小间距 100px
    ↓ Column 列表
模式识别 (spatial/pattern_detector.py)
    └── 检测重复元素（如列表项），聚类到 Block
    ↓ Pattern dict
地域分类 (spatial/region_classifier.py)
    └── 识别页面主要区域（Header/Sidebar/Feed/Footer）
    ↓
Row / Block / Column / Region 结构体
```

**配置参数**（见 `config.py`）：

- `ROW_Y_TOLERANCE = 8` — 行聚类容差
- `COLUMN_MIN_GAP = 100` — 列最小间距
- `PATTERN_BUCKET_WIDTH = 50` — 模式聚类桶宽
- `PATTERN_SIMILARITY_THRESHOLD = 0.6` — 相似度阈值
- `REGION_HEADER_THRESHOLD = 0.08` — Header 高度比
- `REGION_FOOTER_THRESHOLD = 0.92` — Footer 高度比
- `REGION_SIDEBAR_MAX_WIDTH = 0.30` — 侧边栏宽度比

**性能指标**：

- 空间聚合延迟：~100-150ms
- 识别地域数：2-5 个/页

---

### 3. 语义理解层（L3 Semantic）

```
Row/Column/Block/Region
    ↓
卡片识别 (semantic/context.py)
    └── 检测逻辑上聚合的内容块（Button Group / Card / Modal）
    ↓
语义标注
    ├── SearchBox — 搜索框（最小输入宽 250px）
    ├── Card — 内容卡片（最少 2 行）
    ├── Modal — 模态框（屏幕中心±0.1）
    ├── ButtonGroup — 按钮组
    └── Others — 其他
    ↓
Component 结构体 + PageContext
    ├── 类型识别
    ├── 交互指导
    └── 相关元素聚合
```

**关键参数**：

- `CARD_MIN_ROWS = 2` — 卡片最小行数
- `CARD_MAX_WIDTH_RATIO = 0.80` — 卡片最大宽度比
- `SEARCHBOX_MIN_INPUT_WIDTH = 250` — 搜索框最小输入宽度
- `MODAL_CENTER_TOLERANCE = 0.10` — 模态框中心容差

**性能指标**：

- 语义分析延迟：~200-300ms
- 识别 Component 数：20-60 个/页

---

### 4. 完整感知管道流程图

```
                    ┌──────────────────────────────┐
                    │  行动后 / 定时触发感知        │
                    └──────────────────────────────┘
                               ↓
                    ┌──────────────────────────────┐
                    │  scheduler.schedule()         │
                    │  (智能调度器)                  │
                    └──────────────────────────────┘
                        ↓       ↓       ↓       ↓
              ┌─────────┴─────────────────────────┐
              ↓                                   ↓

        [L0 Predict]                    [L1 Full Perception]
        缓存预测 (~0.3ms)                全屏截图 + 解析
        • 检查缓存有效性                  • screen.py (截屏)
        • 缓存 TTL: 15s                  • perception.py (L1)
        • 输出缓存结果                    • spatial.py (L2)
            ↓                            • semantic.py (L3)
                                              ↓
        [L1 Peek]                      [L2 Glance (增量)]
        灰度差分 (~50ms)                 仅重新解析变化区域
        • 与缓存截图对比                  • 识别变化矩形
        • 灰度均方差 > 30                • 仅对该区域运行 L1-L3
        • 无变化 → L0                   • 性能提升 5~10x
        • 边界变化 → L2 (重新聚合区域)         ↓
        • 内容变化 → L3 (全屏重解析)          ↓
              ↓
        ┌─────────────────────────────────────┐
        │  安全机制                            │
        ├─────────────────────────────────────┤
        │ • 连续疯狂操作上限: 4 次            │
        │ • 强制 L3 的关键按键: Enter, F5   │
        │ • 置信度阈值: L0(0.8), L1(0.5),  │
        │              L2(0.3)             │
        └─────────────────────────────────────┘
              ↓
        ┌─────────────────────────────────────┐
        │  SchedulerResult 输出               │
        ├─────────────────────────────────────┤
        │ {                                   │
        │   "level": "L0|L1|L2|L3",           │
        │   "perception": {...},              │
        │   "confidence": 0.0~1.0,            │
        │   "escalation_path": [...],         │
        │   "elapsed_ms": 123                 │
        │ }                                   │
        └─────────────────────────────────────┘
```

---

### 5. 智能调度器（Multi-Level Perception）

**四层递进式感知**：

| 层级   | 名称    | 耗时   | 触发条件   | 输出         |
| ------ | ------- | ------ | ---------- | ------------ |
| **L0** | Predict | ~0.3ms | 缓存有效   | 直接返回缓存 |
| **L1** | Peek    | ~50ms  | 灰度差>0   | 更新元素列表 |
| **L2** | Glance  | ~500ms | 变化区域大 | 增量解析     |
| **L3** | Full    | ~2s    | 内容剧变   | 全屏重解析   |

**关键文件**：

- `xclaw/core/context/scheduler.py` — 调度器核心
- `xclaw/core/context/predict.py` — L0 缓存预测
- `xclaw/core/context/peek.py` — L1 灰度差分
- `xclaw/core/context/glance.py` — L2 增量解析
- `xclaw/core/context/state.py` — 状态持久化

**智能机制**：

- **缓存 TTL**：15 秒（可配置）
- **连续便宜操作上限**：4 次（防止累积偏差）
- **强制 L3 按键**：Enter、F5（页面导航）
- **置信度阈值**：L0→0.8, L1→0.5, L2→0.3（越往上要求越低）
- **差分阈值**：
  - `CONTEXT_DIFF_THRESHOLD_UNCHANGED = 0.01` — 无变化
  - `CONTEXT_DIFF_THRESHOLD_MINOR = 0.15` — 小变化→L2
  - `CONTEXT_GLANCE_FALLBACK_RATIO = 0.6` — 大变化→L3

---

### 6. 执行层（Action）

```
action/
├── mouse.py
│   ├── click(x, y) — 单击/双击
│   ├── drag(src, dst) — 拖拽
│   └── scroll(direction, steps) — 滚动
│
├── keyboard.py
│   ├── type(text) — 打字（中文via剪贴板）
│   └── press(key) — 按键（enter/tab/escape/...）
│
└── humanize.py
    ├── Bezier 曲线移动 (0.3~0.8s)
    └── 随机打字延迟 (0.05~0.15s/字符)
```

**人性化机制**（通过 `XCLAW_HUMANIZE=1` 启用）：

- 鼠标移动：贝塞尔曲线平滑过渡，随机抖动
- 打字延迟：每字符 0.05~0.15s，模拟人类输入
- 随机等待：点击后随机 0.1~0.5s 等待响应

**关键配置**：

- `BEZIER_DURATION_RANGE = (0.3, 0.8)` — 移动时长
- `BEZIER_STEPS = 30` — 曲线分段数
- `TYPE_DELAY_RANGE = (0.05, 0.15)` — 每字符延迟

---

### 7. CLI 入口与命令

[xclaw/cli.py](xclaw/cli.py) — Click 框架定义所有命令：

```bash
# 感知命令
xclaw screen                      # L0~L3 全流程感知
xclaw screen --region 0,0,800,600  # 指定区域截图

# 执行命令
xclaw click <x> <y>              # 单击 → 自动触发 schedule()
xclaw click <x> <y> --double     # 双击
xclaw scroll <direction> <steps>  # 滚动（up/down）
xclaw type <text>                # 打字（中文 via 剪贴板）
xclaw press <key>                # 按键（enter/tab/escape/...）
xclaw wait <seconds>             # 等待

# 所有命令输出 JSON，LLM 可直接解析
```

**JSON 输出示例**：

```json
{
  "status": "ok",
  "level": "L1",
  "confidence": 0.85,
  "escalation_path": ["L0", "L1"],
  "elements": [...],
  "regions": [...],
  "components": [...],
  "elapsed_ms": 45
}
```

---

## 📊 全流程数据流

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. 用户 CLI 调用                                                 │
│    $ xclaw click 100 200                                         │
└─────────────────────────────────────────────────┬───────────────┘
                                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. 全局配置加载 (config.py)                                      │
│    • PROJECT_ROOT, WEIGHTS_DIR, OMNIPARSER_DIR                  │
│    • OmniParser 参数 (model paths, thresholds...)              │
│    • 调度器阈值、人性化参数                                       │
└─────────────────────────────────────────────────┬───────────────┘
                                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. 执行层 (action.mouse)                                         │
│    • pyautogui 发送鼠标点击到系统                                │
│    • 如启用人性化，执行贝塞尔曲线移动 + 随机延迟                   │
└─────────────────────────────────────────────────┬───────────────┘
                                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. 智能调度器 (context.scheduler)                               │
│    ┌──────────────────────────────────────────────────────────┐
│    │ L0 Predict                                               │
│    │ • 检查缓存有效性（15s TTL）                              │
│    │ • 若有效 → 返回缓存结果，耗时 0.3ms ✓                    │
│    │ • 若无效 → 继续 L1                                       │
│    └──────────────────────────────────────────────────────────┘
│                    ↓（缓存过期或无缓存）
│    ┌──────────────────────────────────────────────────────────┐
│    │ L1 Peek (仅当需要新感知)                                  │
│    │ • screen.py: 使用 mss 超快速截图 (~20ms)               │
│    │ • 与缓存截图做灰度差分 (<1ms)                            │
│    │ • 若灰度均方差 < 30 → 无变化，返回缓存 ✓ (50ms总)       │
│    │ • 若灰度均方差 > 30 → 继续 L2                            │
│    └──────────────────────────────────────────────────────────┘
│                    ↓（有显著变化）
│    ┌──────────────────────────────────────────────────────────┐
│    │ L2 Glance (增量感知)                                      │
│    │ • 识别灰度图中的变化矩形                                   │
│    │ • 仅对变化区域运行 L1 感知                                │
│    │ • perception/omniparser.py → 仅 crop 区域               │
│    │ • spatial 聚合变化 + 缓存中不变元素                      │
│    │ • 若变化面积 > 60% 屏幕 → 升级 L3 (~500ms)              │
│    │ • 否则 → 返回增量结果 ✓                                  │
│    └──────────────────────────────────────────────────────────┘
│                    ↓（变化过大）
│    ┌──────────────────────────────────────────────────────────┐
│    │ L3 Full (全屏重解析)                                      │
│    │ • screen.py: 完整截图                                    │
│    │ • perception: 完整 OmniParser 识别                       │
│    │   - YOLO 目标检测                                        │
│    │   - Florence2 图标标题识别                               │
│    │   - OCR 文本识别 (EasyOCR + PaddleOCR)                   │
│    │   - 融合元素 (IoU 去重)                                  │
│    │ • spatial: 行列模式地域聚合                              │
│    │ • semantic: 卡片/模态框识别                              │
│    │ → 返回完整结果 ✓ (~2s)                                   │
│    └──────────────────────────────────────────────────────────┘
│
│    安全检查:
│    • 如果连续 cheap op ≥ 4 次 → 强制 L3
│    • 如果按键在 {Enter, F5} → 强制 L3
│    • 否则按上述规则升级
└─────────────────────────────────────────────────┬───────────────┘
                                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. 状态持久化 (context.state)                                    │
│    • 保存截图、元素、缓存到 .context_state.json                │
│    • 用于下次对比和 L0 预测                                       │
└─────────────────────────────────────────────────┬───────────────┘
                                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. JSON 输出                                                     │
│ {                                                                │
│   "status": "ok",                                                │
│   "level": "L1",          // 实际感知深度                        │
│   "confidence": 0.92,     // 置信度                              │
│   "escalation_path": ["L0", "L1"],  // 升级路径                 │
│   "elapsed_ms": 47,       // 总耗时                              │
│   "elements": [...],      // 识别的元素                          │
│   "regions": [...],       // 页面地域                            │
│   "components": [...]     // 语义 Component                     │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 关键创新点

| 创新                | 说明                             | 性能收益                     |
| ------------------- | -------------------------------- | ---------------------------- |
| **四层感知架构**    | L0→L3 渐进式上升，自适应感知深度 | 99% 场景 <100ms              |
| **智能调度**        | 基于灰度差分自动选择感知深度     | 减少不必要的 GPU 运行        |
| **增量解析 (L2)**   | 仅重新解析变化区域 + 合并缓存    | 性能提升 5~10 倍             |
| **双引擎 OCR**      | EasyOCR + PaddleOCR 互补         | 繁简体 + 手写支持            |
| **人性化控制**      | 贝塞尔曲线鼠标轨迹 + 随机延迟    | 绕过反机器人检测             |
| **缓存 + 状态机**   | 15s TTL 缓存 + 连续操作限制      | 稳定性提升，防止漂移         |
| **Chrome CDP 集成** | DevTools Protocol 获取真实 DOM   | 未来扩展点（可获取隐藏元素） |

---

## 📦 模型权重结构

```
weights/
├── icon_detect/
│   ├── model.pt           # YOLO 权重（79MB）
│   ├── model.yaml         # YOLO 配置
│   └── train_args.yaml    # 训练参数记录
│
└── icon_caption_florence/
    ├── model.safetensors  # Florence2 权重（1.2GB）
    ├── config.json        # 模型配置
    └── generation_config.json  # 生成参数
```

- 通过 `huggingface-hub` CLI 管理下载/上传
- 首次运行会从 Hugging Face Hub 自动下载
- 模型存储在 `WEIGHTS_DIR = PROJECT_ROOT / "weights"`

---

## 🔧 核心配置一览

所有可配置项集中在 `xclaw/config.py`：

```python
# 路径配置
PROJECT_ROOT = Path(os.environ["XCLAW_HOME"]) if "XCLAW_HOME" else ...
SCREENSHOTS_DIR, LOGS_DIR, WEIGHTS_DIR = ...

# OmniParser 配置
OMNIPARSER_CONFIG = {
    "som_model_path": "weights/icon_detect/model.pt",
    "caption_model_name": "florence2",
    "caption_model_path": "weights/icon_caption_florence",
    "BOX_TRESHOLD": 0.01,
}

# 人性化 (XCLAW_HUMANIZE=1 启用)
BEZIER_DURATION_RANGE = (0.3, 0.8)  # 鼠标移动时长
TYPE_DELAY_RANGE = (0.05, 0.15)     # 打字延迟

# L2 空间聚合阈值
ROW_Y_TOLERANCE = 8
COLUMN_MIN_GAP = 100
PATTERN_BUCKET_WIDTH = 50
PATTERN_SIMILARITY_THRESHOLD = 0.6

# L3 语义理解阈值
CARD_MIN_ROWS = 2
SEARCHBOX_MIN_INPUT_WIDTH = 250
MODAL_CENTER_TOLERANCE = 0.10

# 智能调度器
CONTEXT_CACHE_TTL = 15.0            # 缓存过期秒数
CONTEXT_MAX_CONSECUTIVE_CHEAP = 4   # 连续 L0/L1 上限
CONTEXT_CRITICAL_KEYS = {"enter", "f5"}  # 强制 L3 的按键
CONTEXT_CONFIDENCE_L0 = 0.8, L1 = 0.5, L2 = 0.3
```

---

## 🧪 测试覆盖

```
tests/
├── test_block_segmenter.py      # L2 行检测
├── test_column_detector.py      # L2 列检测
├── test_pattern_detector.py     # L2 模式识别
├── test_region_classifier.py    # L2 地域分类
├── test_semantic.py             # L3 语义理解
├── test_context_state.py        # 状态机
├── test_scheduler.py            # 调度器
├── test_glance.py               # L2 增量感知
├── test_peek.py                 # L1 灰度差分
├── test_predict.py              # L0 缓存预测
├── test_scroll.py               # 滚动命令
├── test_cache.py                # 缓存管理
└── test_safety.py               # 安全机制
```

---

## ⚠️ 关键注意事项

### 1. OmniParser 修改

- OmniParser 源码位于 `OmniParser/` 目录，**不要修改源文件**
- `xclaw/core/perception/omniparser.py` 通过 `sys.path.insert` 在运行时注入 `OmniParser/` 到模块搜索路径
- `_patch_paddleocr()` 补丁用于过滤新版 PaddleOCR 不认识的旧参数

### 2. Transformers 版本锁定

- `transformers>=4.40.0,<4.46.0` — **严格锁定**
- 更高版本会导致 Florence2 模型加载失败
- 各版本之间 API 变更较大，升级需谨慎

### 3. PyTorch + CUDA

- 需要 CUDA 12.1 支持
- 通过 `pyproject.toml` 中的私有 PyTorch 源安装
- GPU 驱动版本需 >= 525.105

### 4. 缓存与状态

- 状态文件保存到 `SCREENSHOTS_DIR / ".context_state.json"`
- 长时间未操作后缓存自动过期（15s TTL）
- 手动网页重载（F5）会强制触发 L3

---

## 📚 相关文档

- [README.md](README.md) — 快速开始指南
- [CLAUDE.md](CLAUDE.md) — 开发环境与项目结构
- [xclaw/skills/SKILL.md](xclaw/skills/SKILL.md) — Claude Code 技能文档
- [xclaw/skills/workflow.md](xclaw/skills/workflow.md) — 操作规范与工作流
- [xclaw/skills/commands.md](xclaw/skills/commands.md) — CLI 命令参考
