# X-Claw

跨平台视觉代理框架：截屏 → YOLO + PaddleOCR + Florence-2 感知 → 原生键鼠操作。

支持 Windows (CUDA) + macOS (Apple Silicon MPS/CoreML)。

## 开发环境

- Python 3.12（通过 `.python-version` 锁定）
- 包管理：[uv](https://docs.astral.sh/uv/)
- macOS：`uv sync --extra mac`
- Windows：`uv sync --extra win`（CUDA 12.1 + PyTorch 从 `download.pytorch.org/whl/cu121` 安装）
- 运行命令：`uv run xclaw <command>`

## 全局安装

在项目目录下执行：
```bash
uv tool install --editable . --python 3.12
```
安装后可在任意路径使用 `xclaw` 命令。卸载：`uv tool uninstall xclaw`。

## 关键路径

```
xclaw/
├── config.py              # 全局配置（路径、感知参数、人性化参数）
├── cli.py                 # Click CLI 入口
├── platform/
│   ├── __init__.py        # 导出 PLATFORM / PERCEPTION_CONFIG 单例
│   ├── detect.py          # 平台检测（系统、架构、内存、GPU）
│   ├── gpu.py             # 感知引擎硬件配置（CUDA/MPS/CPU 三分支）
│   └── permissions.py     # macOS 权限检测（辅助功能 + 屏幕录制）
├── core/
│   ├── screen.py          # 截屏（mss）
│   ├── parser.py          # 向后兼容 shim → perception/engine.py
│   ├── pipeline.py        # 两层视觉管线：L1 感知 → L2 空间布局
│   ├── daemon.py          # 守护进程客户端（Unix Socket / Named Pipe）
│   ├── daemon_server.py   # 守护进程服务端（模型常驻内存）
│   ├── browser.py         # Chrome 标签页管理（CDP）
│   ├── perception/
│   │   ├── engine.py      # PerceptionEngine 单例：YOLO + OCR + Florence-2 编排
│   │   ├── omniparser.py  # OmniDetector（YOLO 双后端）+ OmniCaption（Florence-2）
│   │   ├── ocr.py         # PaddleOCR 封装（GPU/CPU 自适应）
│   │   ├── merger.py      # IoU 去重 + YOLO/OCR 空间融合
│   │   └── types.py       # RawElement / TextBox 数据类型
│   ├── context/           # L0-L3 智能感知调度器（7 文件）
│   └── spatial/           # 列检测 + 阅读序（5 文件）
├── action/
│   ├── __init__.py        # 平台路由器（Darwin → Quartz, Windows → ctypes）
│   ├── mouse.py           # 高层点击/滚动接口
│   ├── keyboard.py        # 高层打字/按键接口
│   ├── humanize.py        # 贝塞尔曲线移动、随机延迟
│   ├── mouse_darwin.py    # macOS: Quartz CGEvent 鼠标控制
│   ├── keyboard_darwin.py # macOS: Quartz CGEvent 键盘控制
│   ├── mouse_win32.py     # Windows: ctypes SendInput 鼠标控制
│   └── keyboard_win32.py  # Windows: ctypes SendInput 键盘控制
└── skills/
    ├── SKILL.md           # Claude Code 技能入口
    ├── commands.md        # 命令参考
    └── workflow.md        # 操作规范与典型流程
├── installer/
│   ├── __init__.py        # 安装工具包
│   ├── postinstall.py     # 安装后初始化（目录结构 + 模型下载 + init）
│   └── download_gui.py    # Tkinter 模型下载 GUI
└── skills/
    ├── SKILL.md           # Claude Code 技能入口
    ├── commands.md        # 命令参考
    └── workflow.md        # 操作规范与典型流程
scripts/
├── download_models.py     # 跨平台模型下载（OmniParser V2 + PaddleOCR）
├── export_yolo_onnx.py    # YOLO .pt → .onnx 导出
├── build_installer.py     # 跨平台安装包构建
├── installer.iss          # Windows Inno Setup 脚本
└── macos/
    ├── Info.plist.template # macOS .app 元数据模板
    ├── postinstall.sh      # .pkg 安装后脚本
    └── entitlements.plist  # 签名权限（预留）
```

## 平台适配架构

| 组件 | Windows | macOS Apple Silicon |
|------|---------|---------------------|
| 键鼠控制 | ctypes `SendInput` | Quartz `CGEvent` |
| YOLO 检测 | ONNX CUDA / ultralytics | ONNX CoreML / ultralytics |
| OCR | PaddleOCR GPU | PaddleOCR CPU + MKL-DNN |
| Florence-2 | CUDA FP16 | CPU FP32（MPS 有 gather bug） |
| 守护进程 IPC | Named Pipe | Unix Domain Socket |
| torch 索引 | `pytorch-cu121` | PyPI 默认（MPS） |

- `xclaw/platform/detect.py` 检测系统/架构/内存/GPU
- `xclaw/platform/gpu.py` 根据平台生成 `PerceptionConfig`
- `xclaw/action/__init__.py` 根据 `platform.system()` 路由到对应后端

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标移动和打字延迟 | `0` |
| `XCLAW_CDP_HOST` | Chrome DevTools Protocol 地址 | `127.0.0.1` |
| `XCLAW_CDP_PORT` | Chrome DevTools Protocol 端口 | `9222` |
| `XCLAW_HOME` | 项目根目录路径（仅非 editable 安装时需要） | 自动推算 |
| `XCLAW_DATA` | 用户可写数据目录（截图、日志、模型） | 开发模式=PROJECT_ROOT，安装模式=平台用户目录 |

## 感知引擎

- `PerceptionEngine`（`perception/engine.py`）是感知层单例，懒加载三个子模块：
  - `OmniDetector`：YOLO icon_detect，优先 ONNX Runtime，回退 ultralytics
  - `OCREngine`：PaddleOCR v4 中英双语
  - `OmniCaption`：Florence-2 图标描述，条件式调用（仅无文字覆盖的图标）
- `parser.py` 是向后兼容 shim，直接 re-export `PerceptionEngine`
- 模型目录搜索顺序：`PROJECT_ROOT/models` → `weights/` → `DATA_DIR/models` → `~/.xclaw/models/`
- 模型下载：`uv run python scripts/download_models.py`
- ONNX 导出：`uv run python scripts/export_yolo_onnx.py`

## 守护进程

- `daemon_server.py` 在后台常驻模型，避免每次 CLI 调用冷启动
- `xclaw look` 首次调用自动拉起 daemon
- `xclaw daemon-status` / `xclaw daemon-stop` 管理生命周期
- 空闲 300 秒自动退出
- PID 文件：`~/.xclaw/daemon.pid`

## 模型与 OmniParser 注意事项

- OmniParser 源码位于 `OmniParser/` 目录，**不要修改其中的文件**。
- `transformers` 版本锁定在 `>=4.40.0,<4.46.0`，更高版本会导致 Florence2 模型加载失败。
- 模型存放在 `models/`（首选）或 `weights/`（向后兼容）目录，通过 `huggingface-hub` 下载。

## 配置

所有可配置项集中在 `xclaw/config.py`，不要在其他模块中硬编码路径或参数。

## 测试

```bash
uv run pytest                        # 跑默认测试（排除 gpu/bench）
uv run pytest -m gpu                 # 需要 GPU + 模型
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
3. Tkinter GUI 下载模型（~1.3GB）
4. `xclaw init` 校验权限和模型加载
5. 完成
