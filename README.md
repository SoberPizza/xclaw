# X-Claw

纯视觉、纯键鼠的跨平台桌面代理框架。模拟真人使用电脑的完整认知回路：

**截屏（眼睛）→ YOLO + PaddleOCR + SigLIP 2 感知（视觉皮层）→ 结构化 JSON（语言区）→ OS 原生键鼠操作（手）**

感知层将屏幕像素转化为带编号的元素列表（纯文本 JSON），外部 Agent 的 LLM 仅消费该文本做决策，不接触任何图像数据。

支持 Windows (CUDA) + macOS (Apple Silicon MPS/CoreML)。

## 平台支持

| 平台 | GPU | 键鼠 | 全链路延迟 |
|------|-----|------|-----------|
| Windows + NVIDIA GPU | CUDA 12.x（torch cu121） | ctypes SendInput | ~1-1.5s |
| macOS Apple Silicon (>=16GB) | MPS / CoreML | Quartz CGEvent | ~1.5-2.5s |

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器
- macOS: Apple Silicon, >=16GB 统一内存, 需授权辅助功能 + 屏幕录制权限
- Windows: NVIDIA GPU, CUDA 12.x 兼容驱动

## 安装

```bash
# 克隆项目
git clone <repo-url> && cd xclaw

# macOS
uv sync --extra mac

# Windows
uv sync --extra win

# 下载模型 + 导出 ONNX (~1.5 GB)
uv run python scripts/download_models.py

# 验证安装
uv run xclaw look
```

### 全局安装

```bash
uv tool install --editable . --python 3.12
# 之后可在任意路径使用 xclaw 命令
# 卸载: uv tool uninstall xclaw
```

## 项目结构

```
xclaw/
├── config.py              # 全局配置（路径、感知参数、人性化参数）
├── cli.py                 # Click CLI 入口
├── serve.py               # stdio JSON-line 长驻服务器
├── platform/
│   ├── detect.py          # 平台检测（系统/架构/内存/GPU）
│   ├── gpu.py             # 感知引擎硬件配置（CUDA/MPS/CPU 三分支）
│   └── permissions.py     # macOS 权限检测（辅助功能 + 屏幕录制）
├── core/
│   ├── screen.py          # 截屏（mss）
│   ├── cache.py           # LRU 感知缓存
│   ├── pipeline.py        # 两层视觉管线：L1 感知 → L2 空间布局
│   ├── perception/
│   │   ├── backend.py     # PerceptionBackend 协议（抽象接口）
│   │   ├── engine.py      # PerceptionEngine 单例：委托 backend 编排
│   │   ├── pipeline_backend.py # 默认后端：YOLO + OCR + SigLIP 2
│   │   ├── omniparser.py  # OmniDetector（YOLO 双后端：ONNX / ultralytics）
│   │   ├── siglip_classifier.py # SigLIP 2 B/16 零样本图标分类
│   │   ├── icon_labels.py # 预定义图标分类标签（~65 个）
│   │   ├── ocr.py         # PaddleOCR 封装（GPU/CPU 自适应）
│   │   ├── merger.py      # IoU 去重 + YOLO/OCR 空间融合
│   │   └── types.py       # RawElement / TextBox 数据类型
│   ├── context/           # L0-L3 智能感知调度器
│   │   ├── scheduler.py   # 调度入口：根据动作/状态选择感知等级
│   │   ├── state.py       # 持久化上下文状态
│   │   ├── predict.py     # 预测下次所需感知等级
│   │   ├── peek.py        # L0：快速像素级变化检测
│   │   ├── glance.py      # L1：局部感知（变化区域 + 缓存融合）
│   │   └── scroll.py      # 滚动动作专用感知策略
│   └── spatial/           # 列检测 + 阅读序
│       ├── column_detector.py # 列检测算法
│       ├── row_detector.py    # 行检测算法
│       └── reading_order.py   # 列优先阅读顺序
├── action/
│   ├── __init__.py        # ActionBackend 单例（get_backend/set_backend）
│   ├── backend.py         # ActionBackend 协议（抽象接口）
│   ├── native_backend.py  # NativeActionBackend：委托平台模块 + HumanizeStrategy
│   ├── dry_run_backend.py # DryRunBackend：记录动作不触发 OS 事件（测试用）
│   ├── humanize_strategy.py # HumanizeStrategy 协议 + NoopStrategy / BezierStrategy
│   ├── humanize.py        # bezier_point() 纯数学工具函数
│   ├── mouse.py           # 高层点击/滚动接口（委托 ActionBackend）
│   ├── keyboard.py        # 高层打字/按键接口（委托 ActionBackend）
│   ├── mouse_darwin.py    # macOS: Quartz CGEvent 鼠标
│   ├── keyboard_darwin.py # macOS: Quartz CGEvent 键盘
│   ├── mouse_win32.py     # Windows: ctypes SendInput 鼠标
│   └── keyboard_win32.py  # Windows: ctypes SendInput 键盘
├── installer/
│   ├── postinstall.py     # 安装后初始化（目录结构 + 模型下载 + init）
│   └── download_gui.py    # Tkinter 模型下载 GUI
├── debug/
│   └── pipeline.py        # 调试用管线可视化
└── skills/                # Claude Code 技能定义
scripts/
├── download_models.py     # 跨平台模型下载（OmniParser V2 + SigLIP 2）
├── export_yolo_onnx.py    # YOLO .pt → .onnx 导出
├── build_installer.py     # 跨平台安装包构建
├── installer.iss          # Windows Inno Setup 脚本
└── macos/                 # macOS 安装包资源
models/                    # 模型权重 (gitignored)
```

## CLI 命令

### 感知

```bash
xclaw look                      # 截图 + 智能感知
```

### 鼠标操作

```bash
xclaw click 500 300             # 单击
xclaw click 500 300 --double    # 双击
xclaw scroll down 3             # 向下滚动 3 格
xclaw scroll up 5               # 向上滚动 5 格
```

### 键盘操作

```bash
xclaw type "Hello 你好世界"      # 输入文本（中英文/emoji 原生支持）
xclaw press enter               # 按键
xclaw press cmd+c               # 组合键 (macOS)
xclaw press ctrl+c              # 组合键 (Windows)
```

### 等待

```bash
xclaw wait 2                    # 等待 2 秒
```

### 长驻服务器

```bash
xclaw serve                     # 启动 stdio JSON-line 服务器
```

`xclaw serve` 启动 stdio JSON-line 长驻服务器，模型只加载一次，通过 stdin/stdout 交互。

```
← {"status": "ready", "version": "0.5.0"}     # 启动完成
→ {"command": "look"}                           # 感知
← {"status": "ok", "elements": [...], "_meta": {...}}
→ {"command": "click", "x": 100, "y": 200}     # 动作 + 感知
← {"status": "ok", "action": {...}, "perception": {...}}
```

支持命令：`look` / `click` / `type` / `press` / `scroll` / `wait`。
关闭 stdin 或杀掉进程退出。单线程同步，一次处理一个请求。

## 输出示例

```json
{
  "elements": [
    {"id": 1, "type": "text", "bbox": [24, 40, 90, 57], "content": "Home"},
    {"id": 2, "type": "icon", "bbox": [10, 10, 40, 40], "content": "search icon"}
  ],
  "resolution": [1920, 1080],
  "timing": {
    "capture_ms": 50,
    "yolo_ms": 45,
    "ocr_ms": 180,
    "classify_ms": 30,
    "total_ms": 350
  }
}
```

## 感知架构

```
截屏 (mss)
  │
  ├─→ YOLO icon_detect (ONNX CoreML/CUDA 或 ultralytics)
  │     → 交互元素 bbox
  │
  ├─→ PaddleOCR v5 mobile (CPU)
  │     → 文字区域 + OCR 文本
  │
  └─→ 空间融合 (IoU 去重 + 邻近检测)
        │
        └─→ SigLIP 2 B/16 零样本分类 (条件式: 仅无邻近文字的图标)
              → 图标语义标签
```

SigLIP 2 仅在图标 bbox 边缘距离文字 >= 16px 时触发（条件式调用），紧贴文字的图标直接使用邻近文字作为描述。

## 平台适配

| 组件 | Windows | macOS Apple Silicon |
|------|---------|---------------------|
| 键鼠控制 | ctypes `SendInput` | Quartz `CGEvent` |
| YOLO 检测 | ONNX CUDA / ultralytics | ONNX CoreML / ultralytics |
| OCR | PaddleOCR v5 mobile CPU (PaddlePaddle 3.x) | PaddleOCR v5 mobile CPU (PaddlePaddle 3.x) |
| SigLIP 2 分类 | CUDA FP16 | MPS FP32 |
| torch 索引 | `pytorch-cu121` | PyPI 默认（MPS） |
| PaddlePaddle | `paddlepaddle` CPU (PyPI) | `paddlepaddle` CPU (PyPI) |

### 自定义包索引

项目通过 `[tool.uv.index]` + `[tool.uv.sources]` 配置了一个自定义索引：

- **pytorch-cu121** — Windows/Linux 的 PyTorch CUDA 12.1 wheels

PaddlePaddle 统一使用 PyPI 上的 CPU 版 `paddlepaddle`，OCR ~180ms 不需要 GPU 加速，且避免了 `nvidia-cudnn-cu12` 版本冲突。

## 人性化模式

设置环境变量启用贝塞尔曲线鼠标移动和随机打字延迟：

```bash
XCLAW_HUMANIZE=1 xclaw click 500 300
```

- `XCLAW_HUMANIZE=1` 时自动使用 `BezierStrategy`，否则用 `NoopStrategy`
- 所有操作路径均经过 `HumanizeStrategy` 层，无绕过通道

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标/键盘行为 | `0` |
| `XCLAW_HOME` | 项目根目录路径（仅非 editable 安装时需要） | 自动推算 |
| `XCLAW_DATA` | 用户可写数据目录（截图、日志、模型） | 开发模式=PROJECT_ROOT，安装模式=平台用户目录 |

## 测试

```bash
uv run pytest                        # 默认测试（排除 gpu/bench）
uv run pytest -m gpu                 # GPU + 模型测试
uv run pytest -m integration         # 集成测试（需要 screenshots/）
```

## 安装包构建

轻量安装包仅含 xclaw 源码 + uv 二进制（~30MB），首次启动自动在线安装 Python、依赖和模型。

```bash
# macOS (.pkg)
python scripts/build_installer.py --platform macos    # → dist/XClaw-x.x.x.pkg

# Windows (需要 Inno Setup)
python scripts/build_installer.py --platform windows  # → dist/XClaw-x.x.x-Setup.exe
```

### 路径架构（安装模式 vs 开发模式）

| 路径 | 开发模式 | 安装模式 |
|------|---------|---------|
| `PROJECT_ROOT` | 项目根目录 | `.app/Contents/Resources/xclaw-src` |
| `DATA_DIR` | = PROJECT_ROOT | macOS: `~/Library/Application Support/X-Claw`，Windows: `%LOCALAPPDATA%\X-Claw` |
| `MODELS_DIR` | `PROJECT_ROOT/models` | `DATA_DIR/models` |
| `SCREENSHOTS_DIR` | `PROJECT_ROOT/screenshots` | `DATA_DIR/screenshots` |

### 用户安装流程

1. 双击安装包（.pkg / .exe）
2. 首次启动自动执行 `uv sync` 安装 Python + 依赖（~1.5GB）
3. Tkinter GUI 下载模型（~1.5GB）
4. `xclaw look` 验证感知管线正常工作
5. 完成

## 注意事项

- macOS 首次运行需在系统设置中授权「辅助功能」和「屏幕录制」权限
- 模型下载支持 `HF_ENDPOINT` 环境变量设置镜像（中国用户）
- OmniParser 源码位于 `OmniParser/` 目录
- 图标分类使用 SigLIP 2 B/16（`google/siglip2-base-patch16-224`），文本特征启动时预计算，推理为单次批量前向传播
- 模型存放在 `models/`（首选）或 `weights/`（向后兼容）目录，通过 `huggingface-hub` 下载
