# X-Claw 命令参考

## 感知命令

### `xclaw screen [--region x,y,w,h]`
截取屏幕截图。
```json
{"status": "ok", "image_path": "screenshots/screen_xxx.png", "resolution": [w, h]}
```

### `xclaw parse <image_path>`
用 OmniParser 解析截图，识别屏幕元素。
```json
{
  "status": "ok",
  "image_path": "...",
  "elements": [
    {"id": 0, "type": "text|icon", "bbox": [x1,y1,x2,y2], "center": [cx,cy], "content": "..."},
    ...
  ],
  "resolution": [w, h]
}
```

### `xclaw look [--region x,y,w,h] [--depth l1|l2|l3]`
截图 + 三层解析一步完成。`--depth` 控制解析深度（默认 `l3`）。

- `l1`：仅感知，返回 `elements` 列表（同 `parse`）。
- `l2`：感知 + 空间聚合，返回 `page.regions`（header/footer/sidebar/main）、`page.layout`（single/two-column/three-column）。
- `l3`（默认）：感知 + 空间 + 语义，额外返回 `components`（card/navigation/search_box/action_row/input_field/modal）和 `page.scroll_position`。

```json
{
  "plugin": null,
  "page": {
    "layout": "single",
    "regions": {
      "header": {"bbox": [0,0,1920,37], "block_ids": [0]},
      "main":   {"bbox": [0,41,1920,900], "block_ids": [1,2]},
      "footer": {"bbox": [0,950,1920,1077], "block_ids": [3]}
    },
    "scroll_position": "top"
  },
  "components": {
    "cards": [{"id": 0, "bbox": [...], "element_ids": [...]}],
    "action_row": {"id": 1, "bbox": [...], "element_ids": [...]},
    "input_field": [{"id": 2, "bbox": [...], "element_ids": [...]}]
  },
  "feed_pattern": {"detected": false, "card_count": 0},
  "timing": {"l1_ms": 15000, "l2_ms": 2, "l3_ms": 0}
}
```

L3 组件检测规则摘要：
- **input_field**：`text` 类型、宽高比 > 6:1、宽度 ≥ 100px、内容 ≤ 15 字符。
- **navigation**：位于 header/sidebar 区域、≥ 4 个短文本项（≤ 12 字符）。
- **search_box**：宽输入框 ≥ 250px + 距离 < 80px 的 icon + 内容为空或含搜索关键词。
- **action_row**：≥ 3 个 icon、内容 ≤ 10 字符、icon 数量 ≥ 非 icon 数量。
- **card**：≥ 2 行、含 > 10 字符文本、宽度 < 80% 屏宽。
- **modal**：居中（tolerance 10%）、不贴边、宽度 < 50% 屏宽、高度 < 60% 屏高。

## 浏览器命令

### `xclaw tabs`
列出当前 Chrome 所有打开的标签页（需 Chrome 以 `--remote-debugging-port=9222` 启动）。
```json
{
  "status": "ok",
  "tabs": [
    {"id": "...", "title": "...", "url": "...", "domain": "github.com"},
    ...
  ]
}
```

### `xclaw tab <domain>`
按域名模糊匹配并切换到目标标签页。例如 `xclaw tab github` 会匹配 `github.com`。
```json
{"status": "ok", "action": "switch_tab", "id": "...", "title": "...", "url": "...", "domain": "github.com"}
```

## 操作命令

### `xclaw click <x> <y> [--double]`
点击屏幕坐标。`--double` 双击。

### `xclaw type <text>`
在光标位置输入文本。支持中文（自动走剪贴板）。

### `xclaw press <key>`
按下单个按键。常用键：`enter`, `tab`, `escape`, `backspace`, `space`, `delete`。
组合键示例：`ctrl+a`, `alt+f4`。

### `xclaw scroll <up|down> <amount>`
滚动鼠标滚轮。`amount` 为滚动单位数。

### `xclaw wait <seconds>`
等待指定秒数。
