# X-Claw

纯视觉、纯键鼠的跨平台桌面代理框架。模拟真人使用电脑的完整认知回路：

**截屏（眼睛）→ YOLO + PaddleOCR + MiniCPM-V 感知（视觉皮层）→ 结构化 JSON（语言区）→ OS 原生键鼠操作（手）**

感知层将屏幕像素转化为带编号的元素列表（纯文本 JSON），外部 Agent 的 LLM 仅消费该文本做决策，不接触任何图像数据。

支持 Windows (CUDA) + macOS (Apple Silicon MPS/CoreML)。

## 核心约束（不可违背）

X-Claw 是一个数字人的感官和手脚。以下约束定义了项目的身份边界，任何违反均视为架构缺陷：

1. **唯一信息源是屏幕像素。** 不读取 DOM、不调用无障碍树（Accessibility API）、不使用浏览器 DevTools / CDP、不做进程间内存读取。一切状态信息必须从截屏中重建。

2. **唯一输出通道是 OS 原生键鼠事件。** macOS 通过 Quartz CGEvent、Windows 通过 ctypes SendInput。不注入 JavaScript、不调用应用程序 API。复制粘贴（Cmd/Ctrl+C/V）属于真人正常操作，Agent 可以使用；但禁止将剪贴板作为绕过键鼠的隐蔽数据传输通道。

3. **感知层输出纯文本，LLM 不接触图像。** 感知管线的最终产物是结构化 JSON（元素 ID、bbox、类型、文本内容），外部 Agent 的 LLM 仅基于该文本做推理和决策。不向 LLM 传递截图、不依赖多模态能力、不引入"让 LLM 看一眼图片辅助判断"的回退路径。视觉理解的全部责任由感知层承担。

4. **服务单个 Agent。** 架构为单 Agent 独占设计，不考虑多 Agent 并行、分布式调度、远程 RPC。守护进程常驻模型是为了消除单 Agent 的冷启动延迟，不是为了服务多客户端。

5. **感知层与执行层通过协议解耦，但不引入中间层语义推理。** 感知层输出带编号标注的元素列表，所有高层语义理解（意图识别、任务规划）由外部 LLM 在纯文本域完成。禁止在管线中插入"UI 语义分类器"、"控件类型推断器"、"意图预测器"等中间智能层。

6. **反检测是一等需求。** HumanizeStrategy 不是可选的锦上添花，而是与感知、执行同等重要的核心能力。任何新增的操作路径都必须经过人性化策略层，不允许存在绕过 HumanizeStrategy 的快捷通道。

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
├── __init__.py            # 包入口
├── config.py              # 全局配置（路径、感知参数、人性化参数）
├── cli.py                 # Click CLI 入口
├── platform/
│   ├── __init__.py        # 导出 PLATFORM / PERCEPTION_CONFIG 单例
│   ├── detect.py          # 平台检测（系统、架构、内存、GPU）
│   ├── gpu.py             # 感知引擎硬件配置（CUDA/MPS/CPU 三分支）
│   └── permissions.py     # macOS 权限检测（辅助功能 + 屏幕录制）
├── core/
│   ├── __init__.py
│   ├── screen.py          # 截屏（mss）
│   ├── cache.py           # LRU 感知缓存
│   ├── pipeline.py        # 两层视觉管线：L1 感知 → L2 空间布局
│   ├── backend_registry.py # BackendRegistry：线程安全感知后端注册表
│   ├── daemon.py          # 守护进程客户端（Unix Socket / Named Pipe）
│   ├── daemon_server.py   # 守护进程服务端（模型常驻 + BackendRegistry）
│   ├── perception/
│   │   ├── __init__.py
│   │   ├── backend.py     # PerceptionBackend 协议（抽象接口）
│   │   ├── engine.py      # PerceptionEngine 单例：委托 backend 编排
│   │   ├── pipeline_backend.py # 默认后端：YOLO + OCR + MiniCPM-V
│   │   ├── omniparser.py  # OmniDetector（YOLO 双后端：ONNX / ultralytics）
│   │   ├── minicpm_caption.py # MiniCPM-V 2.0 图标描述
│   │   ├── ocr.py         # PaddleOCR 封装（GPU/CPU 自适应）
│   │   ├── merger.py      # IoU 去重 + YOLO/OCR 空间融合
│   │   └── types.py       # RawElement / TextBox 数据类型
│   ├── context/           # L0-L3 智能感知调度器
│   │   ├── __init__.py
│   │   ├── scheduler.py   # 调度入口：根据动作/状态选择感知等级
│   │   ├── state.py       # 持久化上下文状态
│   │   ├── predict.py     # 预测下次所需感知等级
│   │   ├── peek.py        # L0：快速像素级变化检测
│   │   ├── glance.py      # L1：局部感知（变化区域 + 缓存融合）
│   │   └── scroll.py      # 滚动动作专用感知策略
│   └── spatial/           # 列检测 + 阅读序
│       ├── __init__.py
│       ├── types.py       # 空间数据类型
│       ├── column_detector.py # 列检测算法
│       ├── row_detector.py    # 行检测算法
│       └── reading_order.py   # 列优先阅读顺序
├── action/
│   ├── __init__.py        # ActionBackend 单例（get_backend/set_backend）+ 向后兼容函数
│   ├── backend.py         # ActionBackend 协议（抽象接口）
│   ├── native_backend.py  # NativeActionBackend：委托平台模块 + HumanizeStrategy
│   ├── dry_run_backend.py # DryRunBackend：记录动作不触发 OS 事件（测试用）
│   ├── humanize_strategy.py # HumanizeStrategy 协议 + NoopStrategy / BezierStrategy
│   ├── humanize.py        # bezier_point() 纯数学工具函数
│   ├── mouse.py           # 高层点击/滚动接口（委托 ActionBackend）
│   ├── keyboard.py        # 高层打字/按键接口（委托 ActionBackend）
│   ├── mouse_darwin.py    # macOS: Quartz CGEvent 鼠标（raw 操作 + 机械延迟）
│   ├── keyboard_darwin.py # macOS: Quartz CGEvent 键盘（raw 操作 + 机械延迟）
│   ├── mouse_win32.py     # Windows: ctypes SendInput 鼠标（raw 操作 + 机械延迟）
│   └── keyboard_win32.py  # Windows: ctypes SendInput 键盘（raw 操作 + 机械延迟）
├── installer/
│   ├── __init__.py        # 安装工具包
│   ├── postinstall.py     # 安装后初始化（目录结构 + 模型下载 + init）
│   └── download_gui.py    # Tkinter 模型下载 GUI
├── debug/
│   ├── __init__.py
│   └── pipeline.py        # 调试用管线可视化
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
| MiniCPM-V | CUDA FP16 | CPU FP32（MPS 有 gather bug） |
| 守护进程 IPC | Named Pipe | Unix Domain Socket |
| torch 索引 | `pytorch-cu121` | PyPI 默认（MPS） |

- `xclaw/platform/detect.py` 检测系统/架构/内存/GPU
- `xclaw/platform/gpu.py` 根据平台生成 `PerceptionConfig`
- `xclaw/action/__init__.py` 通过 `ActionBackend` 单例路由，`set_backend()` 可注入自定义后端

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标移动和打字延迟 | `0` |
| `XCLAW_HOME` | 项目根目录路径（仅非 editable 安装时需要） | 自动推算 |
| `XCLAW_DATA` | 用户可写数据目录（截图、日志、模型） | 开发模式=PROJECT_ROOT，安装模式=平台用户目录 |

## 感知引擎

- `PerceptionEngine`（`perception/engine.py`）是感知层单例，委托 `PerceptionBackend` 协议：
  - 默认后端 `PipelineBackend`（`pipeline_backend.py`）组合三个子模块：
    - `OmniDetector`：YOLO icon_detect，优先 ONNX Runtime，回退 ultralytics
    - `OCREngine`：PaddleOCR v4 中英双语
    - `MiniCPMCaption`：MiniCPM-V 2.0 图标描述，条件式调用（仅无文字覆盖的图标）
  - 可通过 `PerceptionEngine(backend=custom)` 注入自定义后端
- 模型目录搜索顺序：`PROJECT_ROOT/models` → `weights/` → `DATA_DIR/models` → `~/.xclaw/models/`
- 模型下载：`uv run python scripts/download_models.py`
- ONNX 导出：`uv run python scripts/export_yolo_onnx.py`

## 执行层架构

- `ActionBackend` 协议（`action/backend.py`）定义 click/type/scroll/hotkey 等操作接口
- `NativeActionBackend`（`action/native_backend.py`）：默认实现，委托平台模块 + `HumanizeStrategy`
- `DryRunBackend`（`action/dry_run_backend.py`）：测试用，记录动作不触发 OS 事件
- `HumanizeStrategy` 协议（`action/humanize_strategy.py`）：
  - `NoopStrategy`：无人性化，直接操作
  - `BezierStrategy`：贝塞尔曲线移动 + 抖动 + 随机延迟
- `XCLAW_HUMANIZE=1` 时自动使用 `BezierStrategy`，否则用 `NoopStrategy`
- 平台后端（`mouse_darwin.py` 等）只含 raw OS 操作 + 机械延迟，不含人性化逻辑
- `set_backend(DryRunBackend())` 可在测试中替换整个执行层

## 守护进程

- `daemon_server.py` 在后台常驻模型，避免每次 CLI 调用冷启动
- `BackendRegistry`（`core/backend_registry.py`）：线程安全的命名后端注册表，支持：
  - 注册/注销感知后端
  - 运行时热切换（`switch()`）
  - 调用统计（call_count / total_ms / error_count）
- `xclaw look` 首次调用自动拉起 daemon
- `xclaw daemon-status` / `xclaw daemon-stop` 管理生命周期
- `xclaw daemon-backends` / `xclaw daemon-switch-backend` / `xclaw daemon-backend-status` 管理感知后端
- 空闲 300 秒自动退出
- PID 文件：`~/.xclaw/daemon.pid`

## 模型与 OmniParser 注意事项

- OmniParser 源码位于 `OmniParser/` 目录，**不要修改其中的文件**。
- 图标描述使用 MiniCPM-V 2.0（`openbmb/MiniCPM-V-2`），无 transformers 版本上限约束。
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
