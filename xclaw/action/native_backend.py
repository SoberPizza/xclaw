"""NativeActionBackend — delegates to platform modules with HumanizeStrategy."""

from __future__ import annotations

import platform

from xclaw.action.humanize_strategy import HumanizeStrategy, NoopStrategy


class NativeActionBackend:
    """Cross-platform action backend using OS-native mouse/keyboard events."""

    def __init__(self, humanize: HumanizeStrategy | None = None):
        self._humanize = humanize or NoopStrategy()
        self._mouse = None
        self._keyboard = None

    def _ensure_platform(self):
        if self._mouse is not None:
            return
        if platform.system() == "Darwin":
            from xclaw.action import mouse_darwin as _m, keyboard_darwin as _k
        else:
            from xclaw.action import mouse_win32 as _m, keyboard_win32 as _k
        self._mouse = _m
        self._keyboard = _k

    # -- ActionBackend protocol --------------------------------------------

    def click(self, x: int, y: int, button: str = "left") -> dict:
        self._ensure_platform()
        fx, fy = self._humanize.move_to_target(x, y, self._mouse.move_to)
        self._humanize.pre_click_delay()
        self._mouse.click(fx, fy, button)
        return {"status": "ok", "action": "click", "x": x, "y": y, "button": button}

    def double_click(self, x: int, y: int) -> dict:
        self._ensure_platform()
        fx, fy = self._humanize.move_to_target(x, y, self._mouse.move_to)
        self._humanize.pre_click_delay()
        self._mouse.double_click(fx, fy)
        return {"status": "ok", "action": "double_click", "x": x, "y": y}

    def move_to(self, x: int, y: int) -> None:
        self._ensure_platform()
        self._mouse.move_to(x, y)

    def scroll(self, direction: str, amount: int, x: int | None = None, y: int | None = None) -> dict:
        self._ensure_platform()
        if x is None or y is None:
            sw, sh = self.screen_size()
            x = x if x is not None else sw // 2
            y = y if y is not None else sh // 2
        self._humanize.move_to_target(x, y, self._mouse.move_to)
        remaining = amount
        while remaining > 0:
            chunk = self._humanize.scroll_chunk(remaining)
            self._mouse.scroll(direction, chunk)
            remaining -= chunk
            if remaining > 0:
                self._humanize.inter_scroll_delay()
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount, "x": x, "y": y}

    def type_text(self, text: str) -> dict:
        self._ensure_platform()
        for char in text:
            self._humanize.type_char_delay()
            self._keyboard.type_text(char)
        return {"status": "ok", "action": "type", "text": text}

    def press_key(self, key: str) -> dict:
        self._ensure_platform()
        self._humanize.pre_key_delay()
        self._keyboard.hotkey(key)
        return {"status": "ok", "action": "press", "key": key}

    def hotkey(self, combo: str) -> None:
        self._ensure_platform()
        self._keyboard.hotkey(combo)

    def screen_size(self) -> tuple[int, int]:
        self._ensure_platform()
        return self._mouse._screen_size()

    def cursor_pos(self) -> tuple[int, int]:
        self._ensure_platform()
        return self._mouse._cursor_pos()
