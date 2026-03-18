# X-Claw

视觉代理框架：截屏 → OmniParser 感知 → 鼠标/键盘操作。

## 开发环境

- Python 3.12（通过 `.python-version` 锁定）
- 包管理：[uv](https://docs.astral.sh/uv/)
- GPU：CUDA 12.1 + PyTorch（从 `download.pytorch.org/whl/cu121` 安装）
- 安装依赖：`uv sync`
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
├── config.py          # 全局配置（路径、OmniParser、人性化参数）
├── cli.py             # Click CLI 入口
├── core/
│   ├── screen.py      # 截屏（mss）
│   ├── parser.py      # OmniParser 封装
│   └── browser.py     # Chrome 标签页管理（CDP）
├── action/
│   ├── mouse.py       # 点击、滚动
│   ├── keyboard.py    # 打字、按键
│   └── humanize.py    # 贝塞尔曲线移动、随机延迟
└── skills/
    ├── SKILL.md         # Claude Code 技能入口
    ├── commands.md      # 命令参考
    └── workflow.md      # 操作规范与典型流程
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `XCLAW_HUMANIZE` | 设为 `1` 启用人性化鼠标移动和打字延迟 | `0` |
| `XCLAW_CDP_HOST` | Chrome DevTools Protocol 地址 | `127.0.0.1` |
| `XCLAW_CDP_PORT` | Chrome DevTools Protocol 端口 | `9222` |
| `XCLAW_HOME` | 项目根目录路径（仅非 editable 安装时需要） | 自动推算 |

## OmniParser 注意事项

- OmniParser 源码位于 `OmniParser/` 目录，**不要修改其中的文件**。
- `parser.py` 通过 `sys.path.insert` 在运行时注入 `OmniParser/` 到模块搜索路径。
- PaddleOCR 已移除：`ocr.py` 中的 `install_paddleocr_stub()` 会在 OmniParser 导入前注入空壳模块，使其模块级 `from paddleocr import PaddleOCR` 成为无害的 no-op（OmniParser 实际走 EasyOCR 分支）。
- `transformers` 版本锁定在 `>=4.40.0,<4.46.0`，更高版本会导致 Florence2 模型加载失败。
- 模型权重存放在 `weights/` 目录（`icon_detect/model.pt` + `icon_caption_florence/`），通过 `huggingface-hub` 下载。

## 配置

所有可配置项集中在 `xclaw/config.py`，不要在其他模块中硬编码路径或参数。
