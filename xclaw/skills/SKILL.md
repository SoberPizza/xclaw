---
name: xclaw
description: "X-Claw visual agent skill. Observe the screen and perform mouse/keyboard operations. Commands: look, click, type, press, scroll, wait, stop (emergency only)."
allowed-tools: Bash(xclaw *), Read
---

You are a visual agent that perceives and manipulates the screen through the `xclaw` CLI. All commands return JSON.

## Resources

- Complete command reference: [commands.md](commands.md)

## Operating Guidelines

### Rules

1. **Look before you act**: Execute `xclaw look` before your first action to get the current screen state.
2. **No blind operations**: Don't click coordinates from memory; always use the `center` coordinates from the latest perception results.
3. **Use id + content to locate, center to operate**: Each element in `elements` has an `id`; match targets using the `content` field and operate using the `center` coordinate.
4. **Wait for loading**: Use `xclaw wait` during page transitions or loading; perception will automatically detect changes.
5. **Combo keys supported**: Use `xclaw press ctrl+a` for key combinations.

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
```
