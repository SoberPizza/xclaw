# X-Claw

纯视觉、纯键鼠的 Windows CUDA 桌面代理框架。模拟真人使用电脑的完整认知回路：

**截屏（眼睛）→ YOLO + RapidOCR + Florence-2 感知（视觉皮层）→ 结构化 JSON（语言区）→ OS 原生键鼠操作（手）**

感知层将屏幕像素转化为带编号的元素列表（纯文本 JSON），外部 Agent 的 LLM 仅消费该文本做决策，不接触任何图像数据。

## 环境要求

- Windows 10/11
- NVIDIA GPU（CUDA 12.x 兼容驱动）
- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url> && cd xclaw

# 2. 安装依赖（自动从 PyTorch CUDA 12.1 索引获取 torch）
uv sync

# 3. 下载模型 + 导出 ONNX (~500 MB)
uv run python scripts/download_models.py

# 4. 验证感知管线
uv run xclaw look
```

> 中国用户可设置 HuggingFace 镜像加速模型下载：
> ```bash
> HF_ENDPOINT=https://hf-mirror.com uv run python scripts/download_models.py
> ```

### 全局安装

```bash
uv tool install --editable . --python 3.12
# 之后可在任意路径使用 xclaw 命令
# 卸载: uv tool uninstall xclaw
```

## CLI 命令

所有命令输出干净 JSON 到 stdout（供 LLM 消费），`DEBUG=1` 时日志输出到 stderr。

### 感知

```bash
xclaw look                              # 截图 + 完整感知，输出 JSON
```

### 鼠标操作

```bash
xclaw click 500 300                     # 左键单击
xclaw click 500 300 --double            # 双击
xclaw click 500 300 --button right      # 右键单击
xclaw move 500 300                      # 移动光标（触发 hover）
xclaw scroll down 3                     # 向下滚动 3 格
xclaw scroll up 5                       # 向上滚动 5 格
xclaw drag 100 200 500 600              # 拖拽
xclaw hold left down --x 500 --y 300    # 按住鼠标键
xclaw hold left up --x 500 --y 300      # 释放鼠标键
xclaw cursor                            # 查询光标位置和屏幕尺寸
```

### 键盘操作

```bash
xclaw type "Hello 你好世界"              # 输入文本（中英文/emoji 原生支持）
echo "管道输入" | xclaw type             # 从 stdin 管道输入 UTF-8 文本
xclaw press enter                       # 按键
xclaw hotkey ctrl+c                     # 组合键
```

### 等待

```bash
xclaw wait 2                            # 等待 2 秒 + 自动感知
```

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

## 感知架构

```
截屏 (mss)
  │
  ├─→ YOLO icon_detect (TensorRT EP / CUDA EP / ultralytics)
  │     → 交互元素 bbox
  │
  ├─→ RapidOCR PPOCRv5 mobile (CUDA)
  │     → 文字区域 + OCR 文本
  │
  └─→ 空间融合 (IoU 去重)
        │
        └─→ Florence-2 caption (条件式: 仅无文字的图标)
              → 图标语义描述
```

Florence-2 仅在图标没有文字覆盖时触发（条件式调用），大幅节省推理时间。

## 人性化模式

设置环境变量启用贝塞尔曲线鼠标移动和随机打字延迟：

```bash
XCLAW_HUMANIZE=1 xclaw click 500 300
```

- `BezierStrategy`：Fitts' Law 距离自适应时长 + 贝塞尔曲线轨迹 + 概率性过冲修正 + 微颤抖
- 所有操作路径均经过 `HumanizeStrategy` 层，无绕过通道

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标/键盘行为 | `0` |
| `XCLAW_HOME` | 项目根目录路径（仅非 editable 安装时需要） | 自动推算 |
| `XCLAW_DATA` | 用户可写数据目录（截图、日志、模型） | 开发模式=项目根目录，安装模式=`%LOCALAPPDATA%\X-Claw` |
| `XCLAW_TRT` | 设为 `0` 禁用 TensorRT EP（回退 CUDA EP） | `1` |
| `DEBUG` | 设为 `1` 启用 CLI 调试日志输出到 stderr | `0` |
| `HF_ENDPOINT` | HuggingFace 镜像 URL（中国用户） | 默认官方 |

## 开发

### 测试

```bash
uv run pytest                        # 默认测试（排除 gpu/bench）
uv run pytest -m gpu                 # 需要 GPU + 模型
```

### 模型管理

```bash
# 重新下载全部模型
uv run python scripts/download_models.py

# 单独重新导出 YOLO ONNX
uv run python scripts/export_yolo_onnx.py
```

模型存放在 `models/` 目录（gitignored），搜索顺序：`PROJECT_ROOT/models` → `weights/` → `DATA_DIR/models` → `~/.xclaw/models/`。

### 安装包构建

```bash
# Windows (需要 Inno Setup)
python scripts/build_installer.py --platform windows  # → dist/XClaw-x.x.x-Setup.exe
```
