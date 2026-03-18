# X-Claw Operating Guidelines

## Rules

1. **Look before you act**: Execute `xclaw look` before your first action to get the current screen state.
2. **No blind operations**: Don't click coordinates from memory; always use the `center` coordinates from the latest perception results.
3. **Confirm after input**: After typing text, check the `_perception` feedback; if confidence is low or there are changes, run `look` to confirm.
4. **Use id for positioning**: Each element in the `elements` list has an `id`; match targets using the `content` field and operate using the `center` coordinate.
5. **Trust auto-perception**: Action commands automatically return the `_perception` field, usually no need for manual `look`.
6. **Wait for loading**: Use `xclaw wait` during page transitions or loading; perception will automatically detect changes.
7. **Leverage structured information**: Use `layout.columns` to understand page layout and `elements[].col` to know which column each element belongs to.

## Perception Feedback Workflow

Action commands (`click`/`type`/`press`/`scroll`/`wait`) automatically run the smart perception scheduler after execution. The returned `_perception` field tells you:

- **`level`**: Which perception level was used (L0/L1/L2)
- **`confidence`**: Confidence level of the current screen cache (0-1)
- **`changed`**: Whether the screen has changed
- **`diff_ratio`**: Ratio of changes

### When You Need Manual `look`

- `_perception.level` is `L0` or `L1` and you are **uncertain** if the cache is accurate
- Need a complete element list (L0/L1 only return summaries)
- Need precise `center` coordinates to perform operations
- Before the first action (no cache)

### When You Don't Need Manual `look`

- `_perception.level` is `L2`: Full parsing results already available
- `_perception.changed` is `false`: Screen unchanged, cache still valid
- `_perception.confidence` > 0.8: High confidence, cache is trustworthy
- Continuous text input (`type`): Small screen changes, confidence decays slowly

## Understanding `look` Output

`xclaw look` returns two layers of structured information by default:

- **`layout.columns`**: Detected columns with `id`, `x_range`, `width_pct`, and `element_count`.
- **`layout.total_elements`**: Total element count with `text_count` and `icon_count` breakdown.
- **`elements`**: All detected elements in reading order, each with `id`, `type`, `bbox`, `center`, `content`, and `col` (column assignment).

If you only need the element list without column detection, use `xclaw look --depth l1`.

## Typical Workflow

```
xclaw look                          # 1. Initial observation (L2 with columns)
# → layout.columns, elements with col assignments
xclaw click 640 30                  # 2. Click search box
# → _perception: {level: "L1", changed: false, confidence: 0.75}
# Screen unchanged, continue
xclaw type "hello world"            # 3. Type text
# → _perception: {level: "L0", confidence: 0.71}
# Confidence acceptable, no need for look
xclaw press enter                   # 4. Press enter (critical key → auto L2)
# → _perception: {level: "L2", confidence: 1.0, ...}
# Automatically returns complete parsing results with new page info
xclaw wait 2                        # 5. Wait for loading
# → _perception: {level: "L1", changed: true, diff_ratio: 0.25}
# Large change detected, may need look
xclaw look                          # 6. Confirm new page state
```

## Using `--no-perceive`

When you only need to execute operations without caring about perception results, use `--no-perceive` to skip auto-perception and save time:

```
xclaw type "a" --no-perceive        # Quick input, don't wait for perception
xclaw type "b" --no-perceive
xclaw type "c" --no-perceive
xclaw look                          # Unified observation after input
```
