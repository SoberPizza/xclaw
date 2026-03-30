# X-Claw Command Reference

## Perception Commands

### `xclaw look`

Observe the screen. Takes a screenshot, diffs against previous state, and automatically decides parsing depth (L0 cache / L1 pixel-diff / L2 full parse). Returns elements and layout.

```json
{
  "layout": {
    "columns": [
      {"id": 0, "x_range": [0, 960], "width_pct": 50, "element_count": 30},
      {"id": 1, "x_range": [960, 1920], "width_pct": 50, "element_count": 25}
    ],
    "total_elements": 55,
    "text_count": 30,
    "icon_count": 25
  },
  "elements": [
    {"id": 0, "type": "text", "bbox": [10,20,200,40], "center": [105,30], "content": "File", "col": 0},
    {"id": 1, "type": "icon", "bbox": [210,20,240,40], "center": [225,30], "content": "menu icon", "col": 0}
  ],
  "timing": {"l1_ms": 9800, "l2_ms": 1},
  "_meta": {
    "level": "L2",
    "confidence": 1.0,
    "changed": true,
    "diff_ratio": 0.35,
    "elapsed_ms": 9801
  }
}
```

## Action Commands

All action commands automatically observe the screen after execution and return `{action, perception, _meta}`.

### `xclaw click <x> <y> [--double] [--button left|right|middle]`

Click at screen coordinates.

- `--double`: perform a double-click
- `--button`: select mouse button (default: `left`)

```bash
xclaw click 500 300                    # left click
xclaw click 500 300 --double           # double click
xclaw click 500 300 --button right     # right click (context menu)
xclaw click 500 300 --button middle    # middle click (open in new tab)
```

### `xclaw type <text>`

Type text at the cursor position. Supports Chinese characters (automatically uses clipboard).

```bash
xclaw type "hello world"
xclaw type "你好世界"
```

### `xclaw press <key>`

Press a single key. For key combinations use `xclaw hotkey` instead.

Common keys: `enter`, `tab`, `escape`, `backspace`, `space`, `delete`, `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`, `f1`-`f12`.

```bash
xclaw press enter
xclaw press tab
xclaw press escape
xclaw press f5
```

### `xclaw hotkey <combo>`

Execute a key combination. Modifier keys: `ctrl`, `shift`, `alt`, `win`.

```bash
xclaw hotkey ctrl+c                    # copy
xclaw hotkey ctrl+v                    # paste
xclaw hotkey ctrl+a                    # select all
xclaw hotkey ctrl+z                    # undo
xclaw hotkey ctrl+shift+t             # reopen closed tab
xclaw hotkey alt+f4                    # close window
xclaw hotkey alt+tab                   # switch window
xclaw hotkey win+d                     # show desktop
xclaw hotkey ctrl+shift+escape        # task manager
```

### `xclaw scroll <up|down|left|right> <amount> [--x X] [--y Y]`

Scroll the mouse wheel. Supports vertical (up/down) and horizontal (left/right) scrolling.

**Parameters:**

- `amount`: Number of scroll units (pixel-level scrolling, **recommended minimum: 500** for noticeable effect)
- `--x`, `--y`: Optional coordinates to position mouse before scrolling (defaults: screen center)

**Scroll Amount Guide:**
| Amount | Visual Effect |
|--------|---------------|
| 5-100 | Barely perceptible |
| 100-300 | Light scroll (a few lines) |
| **500+** | **Recommended - clear visible scroll** |
| 1000+ | Large scroll (major page movement) |

```bash
xclaw scroll down 500                  # scroll down
xclaw scroll up 1000                   # scroll up a lot
xclaw scroll down 500 --x 200 --y 400 # scroll at specific position
xclaw scroll right 500                 # horizontal scroll right (wide tables)
xclaw scroll left 300                  # horizontal scroll left
```

### `xclaw drag <x1> <y1> <x2> <y2> [--button left|right|middle]`

Drag from (x1, y1) to (x2, y2). Mouse button down at start, humanized move, mouse button up at end.

Use cases: drag-and-drop files, resize windows, move sliders, select text, draw selections.

```bash
xclaw drag 100 100 500 400             # drag selection
xclaw drag 50 200 300 200              # move slider horizontally
xclaw drag 960 0 960 500               # resize window (drag title bar down)
xclaw drag 100 50 400 50 --button left # drag file to another location
```

### `xclaw move <x> <y>`

Move cursor to (x, y) without clicking. Triggers hover effects.

Use cases: reveal tooltips, expand dropdown menus on hover, highlight buttons.

```bash
xclaw move 500 300                     # hover over element
xclaw move 100 50                      # hover to reveal tooltip
```

### `xclaw hold <left|right|middle> <down|up> [--x X] [--y Y]`

Press or release a mouse button independently. For complex multi-step interactions where `drag` is not flexible enough.

Coordinates default to current cursor position if not specified.

```bash
xclaw hold left down --x 100 --y 200   # press left button at (100, 200)
xclaw move 300 400                     # move while holding
xclaw hold left up --x 300 --y 400     # release at (300, 400)

# Ctrl+click multi-select pattern:
xclaw hotkey ctrl                       # (use hold for modifier if needed)
xclaw click 100 200                    # click first item
xclaw click 100 300                    # click second item
```

### `xclaw cursor`

Query cursor position and screen size. Returns JSON directly — does NOT trigger perception.

```bash
xclaw cursor
# → {"cursor": [512, 384], "screen": [1920, 1080]}
```

### `xclaw wait <seconds>`

Wait for the specified number of seconds, then observe the screen. Use during page transitions or loading.

```bash
xclaw wait 2                           # wait 2 seconds
xclaw wait 0.5                         # wait 500ms
```

### Action Response Format

Every action command (except `cursor`) returns:

```json
{
  "action": {
    "status": "ok",
    "action": "click",
    "x": 500,
    "y": 300
  },
  "perception": {
    "layout": {...},
    "elements": [...],
    "timing": {...}
  },
  "_meta": {
    "level": "L2",
    "confidence": 1.0,
    "changed": true,
    "diff_ratio": 0.08,
    "elapsed_ms": 400
  }
}
```

### `_meta` Field Reference

| Field | Description |
|-------|-------------|
| `level` | Perception level used: L0 (cache), L1 (pixel-diff), L2 (full parse) |
| `confidence` | Cache confidence (0-1) |
| `changed` | Whether the screen changed since last observation |
| `diff_ratio` | Ratio of changed pixels (0-1) |
| `elapsed_ms` | Perception time in milliseconds |

### Auto-escalation Rules

- Consecutive L0/L1 > 4 times → Force L2
- Cache > 15 seconds → Force L2
- Critical keys like `enter`/`f5` → Force L2
- Any level error → Auto-escalate to next level

## Emergency Commands

### `xclaw stop`

**Emergency only.** Force-kill the perception daemon when it is stuck or crashed. Do NOT use this during normal operation — the daemon exits automatically after 300 seconds of idle time.

```json
{"status": "stopped"}
```
