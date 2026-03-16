# X-Claw 操作规范

## 规则

1. **先看再做**：每次操作前先执行 `xclaw look` 获取当前屏幕状态。
2. **不盲操作**：不要凭记忆点击坐标，必须基于最新 `look` 结果中的 `center` 坐标。
3. **输入后确认**：输入文本后，先 `look` 找到目标按钮，再 `click` 其坐标。
4. **用 id 定位**：`elements` 列表中每个元素有 `id`，用 `content` 字段匹配目标，用 `center` 坐标操作。
5. **操作后验证**：执行关键操作后再次 `look`，确认操作生效。
6. **等待加载**：页面跳转或加载时用 `xclaw wait` 等待，再 `look` 确认。
7. **利用结构化信息**：优先使用 `page.regions` 和 `components` 来理解页面布局，而非逐个扫描元素。

## 理解 look 输出

`xclaw look` 默认返回三层结构化信息：

- **`page.regions`**：页面区域（header / main / footer / sidebar），快速定位目标所在区域。
- **`page.layout`**：布局类型（single / two-column / three-column）。
- **`page.scroll_position`**：滚动位置（top / middle / bottom），判断是否需要滚动。
- **`page.modal_open`**：若存在则表示检测到弹窗，应优先处理弹窗。
- **`components`**：语义组件（card / navigation / search_box / action_row / input_field / modal），每个组件包含 `element_ids` 可回溯到具体元素。

如果只需要元素列表，使用 `xclaw look --depth l1`。
如果只需要区域布局，使用 `xclaw look --depth l2`。

## 典型流程

```
xclaw look                          # 1. 观察屏幕（获取结构化页面信息）
# → page.regions 显示 header 区域 + main 区域
# → components 中有 search_box，element_ids=[3,5]
# → 找到 elements 中 id=5 的输入框，center=[640, 30]
xclaw click 640 30                  # 2. 点击搜索框
xclaw type "hello world"            # 3. 输入文本
xclaw look                          # 4. 再次观察，找到"搜索"按钮
# → 找到 content="搜索" 按钮，center=[750, 30]
xclaw click 750 30                  # 5. 点击按钮
xclaw wait 2                        # 6. 等待加载
xclaw look                          # 7. 确认结果
```
