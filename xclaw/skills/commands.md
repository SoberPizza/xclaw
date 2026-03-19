# X-Claw Command Reference

## Perception Commands

### `xclaw init`

Initialize X-Claw: load OmniParser models and verify GPU/CUDA availability.

```json
{
  "status": "ok",
  "message": "X-Claw initialization complete",
  "components": {
    "omniparser": "ready",
    "device": "cuda"
  }
}
```

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

### `xclaw click <x> <y> [--double]`

Click at screen coordinates. `--double` performs a double-click.

### `xclaw type <text>`

Type text at the cursor position. Supports Chinese characters (automatically uses clipboard).

### `xclaw press <key>`

Press a single key or combination. Common keys: `enter`, `tab`, `escape`, `backspace`, `space`, `delete`.
Combination key examples: `ctrl+a`, `alt+f4`, `ctrl+c`.

### `xclaw scroll <up|down> <amount> [--x X] [--y Y]`

Scroll the mouse wheel.

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

### `xclaw wait <seconds>`

Wait for the specified number of seconds, then observe the screen.

### Action Response Format

Every action command returns:

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
