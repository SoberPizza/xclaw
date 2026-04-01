"""NativeActionBackend — delegates to Windows win32 modules with HumanizeStrategy."""

from __future__ import annotations

from xclaw.action.humanize_strategy import HumanizeStrategy, NoopStrategy


class NativeActionBackend:
    """Windows action backend using ctypes SendInput mouse/keyboard events."""

    def __init__(self, humanize: HumanizeStrategy | None = None):
        self._humanize = humanize or NoopStrategy()
        self._mouse = None
        self._keyboard = None

    def _ensure_platform(self):
        if self._mouse is not None:
            return
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
        self._humanize.move_to_target(x, y, self._mouse.move_to)

    def drag(self, x1: int, y1: int, x2: int, y2: int, button: str = "left") -> dict:
        self._ensure_platform()
        # Move to start position
        fx1, fy1 = self._humanize.move_to_target(x1, y1, self._mouse.move_to)
        self._humanize.pre_drag_delay()
        # Press button down
        self._mouse.mouse_down(fx1, fy1, button)
        self._humanize.pre_drag_delay()
        # Move to end position (with humanized curve)
        fx2, fy2 = self._humanize.move_to_target(x2, y2, self._mouse.move_to)
        self._humanize.pre_drag_delay()
        # Release button
        self._mouse.mouse_up(fx2, fy2, button)
        return {"status": "ok", "action": "drag", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "button": button}

    def mouse_down(self, x: int, y: int, button: str = "left") -> dict:
        self._ensure_platform()
        fx, fy = self._humanize.move_to_target(x, y, self._mouse.move_to)
        self._humanize.pre_click_delay()
        self._mouse.mouse_down(fx, fy, button)
        return {"status": "ok", "action": "mouse_down", "x": x, "y": y, "button": button}

    def mouse_up(self, x: int, y: int, button: str = "left") -> dict:
        self._ensure_platform()
        self._mouse.mouse_up(x, y, button)
        return {"status": "ok", "action": "mouse_up", "x": x, "y": y, "button": button}

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
        segments = self._keyboard._split_text(text)
        has_non_ascii = any(k == "non_ascii" for k, _ in segments)
        has_ascii = any(k == "ascii" for k, _ in segments)

        # Toggle IME to English mode if ASCII segments need VK input
        ime_toggled = False
        if has_ascii and self._keyboard._is_ime_chinese_mode():
            self._keyboard._toggle_ime_to_english()
            ime_toggled = True

        for kind, segment in segments:
            if kind == "control":
                for char in segment:
                    if char == "\r":
                        continue  # skip CR (CRLF; \n handles Enter)
                    self._humanize.type_char_delay()
                    self._keyboard._press_release_vk(
                        self._keyboard.WIN_VK["return"] if char == "\n"
                        else self._keyboard.WIN_VK["tab"]
                    )
            elif kind == "ascii":
                for char in segment:
                    self._humanize.type_char_delay()
                    self._keyboard.type_char_vk(char)
            else:
                # non_ascii: whole segment via IME composition,
                # falling back to clipboard paste if IME unavailable
                self._humanize.type_char_delay()
                if not self._keyboard.ime_compose(segment):
                    self._keyboard.clipboard_paste(segment)

        if ime_toggled:
            self._keyboard._toggle_ime_to_english()

        return {"status": "ok", "action": "type", "text": text}

    def press_key(self, key: str) -> dict:
        self._ensure_platform()
        self._humanize.pre_key_delay()
        self._keyboard.hotkey(key)
        return {"status": "ok", "action": "press", "key": key}

    def hotkey(self, combo: str) -> None:
        self._ensure_platform()
        self._humanize.pre_key_delay()
        self._keyboard.hotkey(combo)

    def screen_size(self) -> tuple[int, int]:
        self._ensure_platform()
        return self._mouse._screen_size()

    def cursor_pos(self) -> tuple[int, int]:
        self._ensure_platform()
        return self._mouse._cursor_pos()
