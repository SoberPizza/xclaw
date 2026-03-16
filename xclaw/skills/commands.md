# X-Claw Command Reference

## Perception Commands

### `xclaw screen [--region x,y,w,h]`

Capture a screenshot of the screen.

```json
{"status": "ok", "image_path": "screenshots/screen_xxx.png", "resolution": [w, h]}
```

### `xclaw parse <image_path>`

Parse a screenshot using OmniParser to identify screen elements.

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

Capture screenshot and perform three-layer parsing in one step. The `--depth` flag controls parsing depth (default: `l3`). Always executes the complete L3 pipeline, unaffected by the scheduler. After execution, updates ContextState (confidence reset to 1.0).

- `l1`: Perception only, returns `elements` list (same as `parse`).
- `l2`: Perception + spatial aggregation, returns `page.regions` (header/footer/sidebar/main) and `page.layout` (single/two-column/three-column).
- `l3` (default): Perception + spatial + semantic, additionally returns `components` (card/navigation/search_box/action_row/input_field/modal) and `page.scroll_position`.

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

L3 Component Detection Rules Summary:

- **input_field**: `text` type, aspect ratio > 6:1, width ≥ 100px, content ≤ 15 characters.
- **navigation**: Located in header/sidebar area, ≥ 4 short text items (≤ 12 characters).
- **search_box**: Wide input field ≥ 250px + icon within distance < 80px + content is empty or contains search keywords.
- **action_row**: ≥ 3 icons, content ≤ 10 characters, icon count ≥ non-icon count.
- **card**: ≥ 2 rows, contains > 10 character text, width < 80% screen width.
- **modal**: Centered (tolerance 10%), not edge-aligned, width < 50% screen width, height < 60% screen height.

### `xclaw peek`

L1 pixel diff — No GPU usage, only compares pixel differences between the current and previous screenshot.

```json
{
  "level": "L1",
  "changed": true,
  "diff_ratio": 0.032,
  "change_regions": [[100, 100, 200, 200]],
  "elapsed_ms": 48
}
```

### `xclaw glance`

L2 incremental parsing — First detect changed regions with peek, then run OmniParser only on changed regions and merge with cached elements. Degrades to L1 if no changes are detected.

```json
{
  "level": "L2",
  "merged_from_cache": 15,
  "newly_parsed": 3,
  "elapsed_ms": 380,
  "page": { ... },
  "components": { ... },
  "timing": {"glance_ms": 380}
}
```

### `xclaw status`

Pixel-level diff change detection (same as `peek`, maintained for backward compatibility).

```json
{"changed": true, "diff_ratio": 0.032, "change_regions": [...], "elapsed_ms": 48}
```

## Browser Commands

### `xclaw tabs`

List all open tabs in Chrome (requires Chrome to be started with `--remote-debugging-port=9222`).

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

Fuzzy match by domain and switch to target tab. For example, `xclaw tab github` will match `github.com`.

```json
{
  "status": "ok",
  "action": "switch_tab",
  "id": "...",
  "title": "...",
  "url": "...",
  "domain": "github.com"
}
```

## Action Commands

All action commands automatically run the smart perception scheduler after execution and return the `_perception` field. Use `--no-perceive` to skip.

### `xclaw click <x> <y> [--double] [--no-perceive]`

Click at screen coordinates. `--double` performs a double-click.

### `xclaw type <text> [--no-perceive]`

Type text at the cursor position. Supports Chinese characters (automatically uses clipboard).

### `xclaw press <key> [--no-perceive]`

Press a single key. Common keys: `enter`, `tab`, `escape`, `backspace`, `space`, `delete`.
Combination key examples: `ctrl+a`, `alt+f4`.

### `xclaw scroll <up|down> <amount> [--x X] [--y Y] [--no-perceive]`

Scroll the mouse wheel.

**Parameters:**

- `amount`: Number of scroll units (pixel-level scrolling, **recommended minimum: 500** for noticeable effect)
- `--x`, `--y`: Optional coordinates to position mouse before scrolling (defaults: screen center)

**Important Notes:**

- The `amount` parameter operates at **pixel-level granularity**. Values below 500 may produce minimal or imperceptible results.
- Always move the mouse to the target area first. Use `--x` and `--y` to position, or click before scrolling.
- Effective for scrollable content (browser windows, text areas, lists).

**Examples:**

```bash
# Scroll down 500 pixels at screen center
xclaw scroll down 500 --no-perceive

# Scroll up at specific coordinates
xclaw scroll up 500 --x=500 --y=400 --no-perceive

# Click first to focus, then scroll
xclaw click 500 400
xclaw scroll down 500
```

**Scroll Amount Guide:**
| Amount | Visual Effect |
|--------|---------------|
| 5-100 | Barely perceptible |
| 100-300 | Light scroll (a few lines) |
| **500+** | **Recommended - clear visible scroll** |
| 1000+ | Large scroll (major page movement) |

### `xclaw wait <seconds> [--no-perceive]`

Wait for the specified number of seconds.

### `_perception` Field

The output of action commands automatically includes a `_perception` field containing perception feedback:

```json
{
  "status": "ok",
  "action": "click",
  "x": 500,
  "y": 300,
  "_perception": {
    "level": "L1",
    "confidence": 0.92,
    "changed": false,
    "diff_ratio": 0.003,
    "elapsed_ms": 48
  }
}
```

**Perception Level Explanation**:
| Level | Meaning | GPU | Latency |
|-------|---------|-----|----------|
| L0 | Confidence prediction, returns cached result | None | ~0ms |
| L1 | Pixel diff, returns cache if unchanged | None | ~50ms |
| L2 | Local crop parsing + cache merge | Minimal | ~400ms |
| L3 | Complete three-layer pipeline (same as `look`) | Full | ~1.5s |

**Auto-escalation Rules**:

- Consecutive L0/L1 > 4 times → Force L3
- Cache > 15 seconds → Force L3
- Critical keys like `enter`/`f5` → Force L3
- Any level error → Auto-escalate to next level
