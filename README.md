# X-Claw

跨平台 CLI 视觉代理工具，让大模型通过终端命令控制桌面，完成自动化交互。

基于 YOLO + PaddleOCR + Florence-2 实现屏幕元素识别，通过原生 API（macOS Quartz / Windows ctypes）执行鼠标键盘操作。所有命令输出 JSON，方便 LLM 解析。

## 平台支持

| 平台 | GPU | 键鼠 | 全链路延迟 |
|------|-----|------|-----------|
| Windows + NVIDIA GPU | CUDA 12.1 | ctypes SendInput | ~1-1.5s |
| macOS Apple Silicon (>=16GB) | MPS / CoreML | Quartz CGEvent | ~1.5-2.5s |

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器
- macOS: Apple Silicon, >=16GB 统一内存, 需授权辅助功能 + 屏幕录制权限
- Windows: NVIDIA GPU, CUDA 12.1

## 安装

```bash
# 克隆项目
git clone <repo-url> && cd xclaw

# macOS
uv sync --extra mac

# Windows
uv sync --extra win

# 下载模型 (~1.3 GB)
uv run python scripts/download_models.py

# (可选) 导出 YOLO ONNX 加速
uv run python scripts/export_yolo_onnx.py

# 验证安装
uv run xclaw init
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
├── config.py              # 全局配置
├── cli.py                 # CLI 入口
├── platform/
│   ├── detect.py          # 平台检测（系统/架构/内存/GPU）
│   ├── gpu.py             # 感知引擎硬件配置
│   └── permissions.py     # macOS 权限检测
├── core/
│   ├── perception/
│   │   ├── engine.py      # PerceptionEngine: YOLO + OCR + Florence-2
│   │   ├── omniparser.py  # OmniDetector + OmniCaption
│   │   ├── ocr.py         # PaddleOCR 封装
│   │   ├── merger.py      # 空间融合 + IoU 去重
│   │   └── types.py       # RawElement / TextBox
│   ├── pipeline.py        # L1 感知 → L2 空间布局
│   ├── context/           # L0-L3 智能感知调度
│   ├── spatial/           # 列检测 + 阅读序
│   ├── daemon.py          # 守护进程客户端
│   └── daemon_server.py   # 守护进程服务端
├── action/
│   ├── __init__.py        # 平台路由 (Darwin/Windows)
│   ├── mouse.py           # 高层鼠标接口
│   ├── keyboard.py        # 高层键盘接口
│   ├── humanize.py        # 贝塞尔曲线 + 随机延迟
│   ├── mouse_darwin.py    # macOS Quartz CGEvent
│   ├── keyboard_darwin.py # macOS Quartz CGEvent
│   ├── mouse_win32.py     # Windows ctypes SendInput
│   └── keyboard_win32.py  # Windows ctypes SendInput
└── skills/                # Claude Code 技能定义
scripts/
├── download_models.py     # 模型下载
└── export_yolo_onnx.py    # YOLO ONNX 导出
models/                    # 模型权重 (gitignored)
```

## CLI 命令

### 初始化 & 感知

```bash
xclaw init                      # 检查权限、加载模型、报告设备信息
xclaw look                      # 截图 + 智能感知（自动拉起 daemon）
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

### 守护进程

```bash
xclaw daemon-status             # 检查 daemon 状态
xclaw daemon-stop               # 停止 daemon
```

`look` 命令首次调用自动拉起守护进程（模型常驻内存），后续调用无冷启动。空闲 5 分钟自动退出。

## 输出示例

```json
{
  "elements": [
    {"id": 1, "type": "text", "bbox": [24, 40, 90, 57], "content": "Home"},
    {"id": 2, "type": "icon", "bbox": [10, 10, 40, 40], "content": "Navigation menu"}
  ],
  "resolution": [1920, 1080],
  "timing": {
    "capture_ms": 50,
    "yolo_ms": 45,
    "ocr_ms": 180,
    "caption_ms": 500,
    "total_ms": 820
  }
}
```

## 人性化模式

设置环境变量启用贝塞尔曲线鼠标移动和随机打字延迟：

```bash
XCLAW_HUMANIZE=1 xclaw click 500 300
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标/键盘行为 | `0` |
| `XCLAW_HOME` | 项目根目录路径（仅非 editable 安装时需要） | 自动推算 |

## 感知架构

```
截屏 (mss)
  │
  ├─→ YOLO icon_detect (ONNX CoreML/CUDA 或 ultralytics)
  │     → 交互元素 bbox
  │
  ├─→ PaddleOCR v4 (GPU/CPU)
  │     → 文字区域 + OCR 文本
  │
  └─→ 空间融合 (IoU 去重)
        │
        └─→ Florence-2 caption (条件式: 仅无文字的图标)
              → 图标语义描述
```

Florence-2 仅在图标没有文字覆盖时触发（条件式调用），大幅节省推理时间。

## 注意事项

- `transformers` 版本锁定在 `<4.46.0` 以兼容 Florence-2 模型
- macOS 首次运行需在系统设置中授权「辅助功能」和「屏幕录制」权限，`xclaw init` 会自动引导
- 模型下载支持 `HF_ENDPOINT` 环境变量设置镜像（中国用户）

## 测试

```bash
uv run pytest                        # 默认测试（排除 gpu/bench）
uv run pytest -m gpu                 # GPU + 模型测试
uv run pytest -m integration         # 集成测试（需要 screenshots/）
```
