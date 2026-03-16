# X-Claw

CLI 视觉代理工具，让大模型通过终端命令控制 Windows 桌面上的 Chrome 浏览器，完成 X/Twitter 自动化交互。

基于 OmniParser V2 实现屏幕元素识别，通过 pyautogui 执行鼠标键盘操作。所有命令输出 JSON，方便 LLM 解析。

## 环境要求

- Python >= 3.12
- Windows（pyautogui 控制桌面）
- CUDA 12.1（GPU 推理）
- [uv](https://docs.astral.sh/uv/) 包管理器

## 安装

```bash
# 克隆项目
git clone <repo-url> && cd xclaw

# 安装依赖
uv sync

# 下载 OmniParser V2 权重（已放在 weights/ 目录）
# weights/icon_detect/model.pt
# weights/icon_caption_florence/model.safetensors
```

## 项目结构

```
xclaw/
├── cli.py                  # CLI 入口，所有命令定义
├── core/
│   ├── screen.py           # mss 截图
│   └── parser.py           # OmniParser 包装层
└── action/
    ├── mouse.py            # 鼠标点击、滚动
    ├── keyboard.py         # 键盘输入、按键
    └── humanize.py         # 贝塞尔曲线鼠标轨迹 + 随机打字延迟
OmniParser/                 # OmniParser V2 源码（sys.path 注入）
weights/                    # 模型权重
screenshots/                # 截图输出目录（gitignored）
logs/                       # 解析 JSON 日志（gitignored）
```

## CLI 命令

### 截图

```bash
xclaw screen                    # 全屏截图
xclaw screen --region 0,0,800,600  # 指定区域截图
```

输出：`{"status": "ok", "image_path": "screenshots/screen_xxx.png", "resolution": [1920, 1080]}`

### 鼠标操作

```bash
xclaw click 500 300             # 单击
xclaw click 500 300 --double    # 双击
xclaw scroll down 3             # 向下滚动 3 格
xclaw scroll up 5               # 向上滚动 5 格
```

### 键盘操作

```bash
xclaw type "hello world"        # 输入文本（支持中文，自动走剪贴板）
xclaw press enter               # 按键（enter/tab/escape/backspace/...）
```

### 等待

```bash
xclaw wait 2                    # 等待 2 秒
```

### 屏幕解析（OmniParser）

```bash
xclaw parse screenshots/screen_xxx.png   # 解析截图中的 UI 元素
```

输出：

```json
{
  "status": "ok",
  "image_path": "screenshots/screen_xxx.png",
  "elements": [
    {"id": 0, "type": "text", "bbox": [24, 40, 90, 57], "center": [57, 48], "content": "Home"},
    {"id": 1, "type": "icon", "bbox": [10, 10, 40, 40], "center": [25, 25], "content": "Navigation"}
  ],
  "resolution": [1920, 1080]
}
```

解析结果同时保存到 `logs/screen_xxx.json`。

### 一步到位：截图 + 解析

```bash
xclaw look                      # 截图 + OmniParser 解析
xclaw look --region 0,0,800,600
```

## 人性化模式

设置环境变量启用贝塞尔曲线鼠标移动和随机打字延迟：

```bash
XCLAW_HUMANIZE=1 xclaw click 500 300
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标/键盘行为 |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | 设为 `True` 跳过 PaddleOCR 连接检查（推荐） |

## 注意事项

- `parse` / `look` 命令首次运行会加载模型，冷启动约 3-5 秒
- `screen` / `click` / `type` 等 P0 命令不触发模型加载，响应即时
- pyautogui failsafe 保持开启：鼠标移到屏幕左上角 (0,0) 会触发安全中断
- `transformers` 版本锁定在 `<4.46.0` 以兼容 Florence-2 模型
