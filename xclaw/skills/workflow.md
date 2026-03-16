# X-Claw Operating Guidelines

## Rules

1. **Look before you act**: Execute `xclaw look` before your first action to get the current screen state.
2. **No blind operations**: Don't click coordinates from memory; always use the `center` coordinates from the latest perception results.
3. **Confirm after input**: After typing text, check the `_perception` feedback; if confidence is low or there are changes, run `look` to confirm.
4. **Use id for positioning**: Each element in the `elements` list has an `id`; match targets using the `content` field and operate using the `center` coordinate.
5. **Trust auto-perception**: Action commands automatically return the `_perception` field, usually no need for manual `look`.
6. **Wait for loading**: Use `xclaw wait` during page transitions or loading; perception will automatically detect changes.
7. **Leverage structured information**: Prioritize using `page.regions` and `components` to understand page layout rather than scanning elements one by one.

## Perception Feedback Workflow

Action commands (`click`/`type`/`press`/`scroll`/`wait`) automatically run the smart perception scheduler after execution. The returned `_perception` field tells you:

- **`level`**: Which perception level was used (L0/L1/L2/L3)
- **`confidence`**: Confidence level of the current screen cache (0-1)
- **`changed`**: Whether the screen has changed
- **`diff_ratio`**: Ratio of changes

### When You Need Manual `look`

- `_perception.level` is `L0` or `L1` and you are **uncertain** if the cache is accurate
- Need a complete element list (L0/L1 only return summaries)
- Need precise `center` coordinates to perform operations
- Before the first action (no cache)

### When You Don't Need Manual `look`

- `_perception.level` is `L2` or `L3`: Full parsing results already available
- `_perception.changed` is `false`: Screen unchanged, cache still valid
- `_perception.confidence` > 0.8: High confidence, cache is trustworthy
- Continuous text input (`type`): Small screen changes, confidence decays slowly

## Understanding `look` Output

`xclaw look` returns three layers of structured information by default:

- **`page.regions`**: Page regions (header / main / footer / sidebar), quickly locate which region the target is in.
- **`page.layout`**: Layout type (single / two-column / three-column).
- **`page.scroll_position`**: Scroll position (top / middle / bottom), determine if scrolling is needed.
- **`page.modal_open`**: If present, indicates a modal is detected; should prioritize handling the modal.
- **`components`**: Semantic components (card / navigation / search_box / action_row / input_field / modal), each component contains `element_ids` to trace back to specific elements.

If you only need the element list, use `xclaw look --depth l1`.
If you only need region layout, use `xclaw look --depth l2`.

## Typical Workflow

```
xclaw look                          # 1. Initial observation (complete L3 parsing)
# → page.regions, components, elements
xclaw click 640 30                  # 2. Click search box
# → _perception: {level: "L1", changed: false, confidence: 0.75}
# Screen unchanged, continue
xclaw type "hello world"            # 3. Type text
# → _perception: {level: "L0", confidence: 0.71}
# Confidence acceptable, no need for look
xclaw press enter                   # 4. Press enter (critical key → auto L3)
# → _perception: {level: "L3", confidence: 1.0, ...}
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
