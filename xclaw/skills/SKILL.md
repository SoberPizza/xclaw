---
name: xclaw
description: "X-Claw visual agent skill. Observe the screen and perform mouse/keyboard operations. Commands: look, click, type, press, hotkey, scroll, drag, move, hold, cursor, wait, stop (emergency only)."
allowed-tools: Bash(xclaw *), Read
---

You are a visual agent that perceives and manipulates the screen through the `xclaw` CLI. All commands return JSON.

## Resources

- Complete command reference: [commands.md](commands.md)

## Available Commands

| Command | Description |
|---------|-------------|
| `xclaw look` | Observe screen (screenshot + perception) |
| `xclaw click <x> <y>` | Click at coordinates (`--double`, `--button right\|middle`) |
| `xclaw type <text>` | Type text at cursor |
| `xclaw press <key>` | Press a single key (enter, tab, escape, ...) |
| `xclaw hotkey <combo>` | Key combination (ctrl+c, alt+f4, ctrl+shift+t) |
| `xclaw scroll <dir> <amount>` | Scroll up/down/left/right (`--x`, `--y`) |
| `xclaw drag <x1> <y1> <x2> <y2>` | Drag between two points (`--button`) |
| `xclaw move <x> <y>` | Move cursor without clicking (hover) |
| `xclaw hold <button> <down\|up>` | Press/release mouse button (`--x`, `--y`) |
| `xclaw cursor` | Query cursor position + screen size |
| `xclaw wait <seconds>` | Wait then observe |
| `xclaw stop` | Emergency: kill stuck daemon |

## Operating Guidelines

### Rules

1. **Look before you act**: Execute `xclaw look` before your first action to get the current screen state.
2. **No blind operations**: Don't click coordinates from memory; always use the `center` coordinates from the latest perception results.
3. **Use id + content to locate, center to operate**: Each element in `elements` has an `id`; match targets using the `content` field and operate using the `center` coordinate.
4. **Wait for loading**: Use `xclaw wait` during page transitions or loading; perception will automatically detect changes.
5. **Use hotkey for combos**: Use `xclaw hotkey ctrl+a` for key combinations; use `xclaw press` for single keys only.
6. **Right-click for context menus**: Use `xclaw click X Y --button right` to open context menus.

Every action automatically returns full screen state, so you only need to manually `look` at the start of a session.

### Typical Workflow

```
xclaw look                          # 1. Initial observation
# → layout, elements, timing, _meta
xclaw click 640 30                  # 2. Click search box
# → {action, perception, _meta}
xclaw type "hello world"            # 3. Type text
# → {action, perception, _meta}
xclaw press enter                   # 4. Press enter (critical key → auto L2)
# → {action, perception: {layout: {...}, elements: [...]}, _meta: {level: "L2"}}
xclaw wait 2                        # 5. Wait for loading
# → {action, perception, _meta}
xclaw hotkey ctrl+a                 # 6. Select all
xclaw hotkey ctrl+c                 # 7. Copy
xclaw click 500 300 --button right  # 8. Right-click for context menu
xclaw drag 100 100 500 400          # 9. Drag selection
```
