---
name: xclaw
description: "X-Claw visual agent skill. Observe the screen and perform mouse/keyboard operations. Commands: look, click, type, press, hotkey, scroll, drag, move, hold, cursor, wait."
allowed-tools: Bash(xclaw *), Read
---

You are a visual agent that perceives and manipulates the screen through the `xclaw` CLI. All commands return JSON.

## Rules

1. **Look before you act**: Execute `xclaw look` before your first action to get the current screen state.
2. **No blind operations**: Don't click coordinates from memory; always use the `center` coordinates from the latest perception results.
3. **Use id + content to locate, center to operate**: Each element in `elements` has an `id`; match targets using the `content` field and operate using the `center` coordinate.
4. **Wait for loading**: Use `xclaw wait` during page transitions or loading.
5. **Use hotkey for combos**: Use `xclaw hotkey ctrl+a` for key combinations; use `xclaw press` for single keys only.
6. **Right-click for context menus**: Use `xclaw click X Y --button right`.

Every action automatically returns full screen state, so you only need to manually `look` at the start of a session.

## Commands

### `xclaw look`

Observe the screen. Screenshot → diff → auto perception.

```json
{
  "status": "ok",
  "element_count": 122
  "elements": [
    {"id": 0, "type": "text", "bbox": [10,20,200,40], "center": [105,30], "content": "File", "col": 0},
    {"id": 1, "type": "icon", "bbox": [210,20,240,40], "center": [225,30], "content": "menu icon", "col": 0}
  ],
}
```

### `xclaw click <x> <y> [--double] [--button left|right|middle]`

Click at screen coordinates. `--double` for double-click, `--button right` for context menu.

### `xclaw type <text>`

Type text at cursor. ASCII → physical key simulation; non-ASCII (Chinese, emoji) → KEYEVENTF_UNICODE.

Pure ASCII can use direct argument: `xclaw type "hello world"`

### `xclaw press <key>`

Press a single key. Common: `enter`, `tab`, `escape`, `backspace`, `space`, `delete`, `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`, `f1`–`f12`.

### `xclaw hotkey <combo>`

Key combination. Modifiers: `ctrl`, `shift`, `alt`, `win`.

```bash
xclaw hotkey ctrl+c          # copy
xclaw hotkey ctrl+v          # paste
xclaw hotkey ctrl+a          # select all
xclaw hotkey alt+f4          # close window
xclaw hotkey alt+tab         # switch window
```

### `xclaw scroll <up|down|left|right> <amount> [--x X] [--y Y]`

Scroll mouse wheel. Amount of **minimum 5 recommended**. `--x`/`--y` set scroll position (default: screen center).

| Amount | Effect |
|--------|--------|
| 1–3 | Light scroll (a few lines) |
| **5+** | **Recommended** |
| 10+ | Large page movement |

### `xclaw drag <x1> <y1> <x2> <y2> [--button left|right|middle]`

Drag from (x1,y1) to (x2,y2). Use for: drag-and-drop, resize, sliders, text selection.

### `xclaw move <x> <y>`

Move cursor without clicking. Triggers hover effects / tooltips.

### `xclaw hold <left|right|middle> <down|up> [--x X] [--y Y]`

Press/release mouse button independently. For multi-step interactions where `drag` isn't flexible enough.

```bash
xclaw hold left down --x 100 --y 200
xclaw move 300 400
xclaw hold left up --x 300 --y 400
```

### `xclaw cursor`

Query cursor position + screen size. Does NOT trigger perception.

```bash
xclaw cursor
# → {"cursor": [512, 384], "screen": [1920, 1080]}
```

### `xclaw wait <seconds>`

Wait then observe. Use during page transitions or loading.

## Response Format

All action commands (except `cursor`) return:

```json
{"action": {"status": "ok", ...}, "perception": {"layout": {...}, "elements": [...]}}

```

## Typical Workflow

```
xclaw look                            # 1. Initial observation
xclaw click 640 30                    # 2. Click target element
xclaw type "hello world"              # 3. Type text
xclaw press enter                     # 4. Confirm
xclaw wait 2                          # 5. Wait for loading
xclaw hotkey ctrl+a                   # 6. Select all
xclaw click 500 300 --button right    # 7. Right-click context menu
```
