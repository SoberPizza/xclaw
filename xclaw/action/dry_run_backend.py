"""DryRunBackend — records all actions without triggering OS events."""

from __future__ import annotations


class DryRunBackend:
    """Records actions in a log list. Useful for testing and debugging."""

    def __init__(self):
        self.log: list[dict] = []

    def _record(self, **kwargs) -> dict:
        entry = {"status": "ok", **kwargs}
        self.log.append(entry)
        return entry

    def click(self, x: int, y: int, button: str = "left") -> dict:
        return self._record(action="click", x=x, y=y, button=button)

    def double_click(self, x: int, y: int) -> dict:
        return self._record(action="double_click", x=x, y=y)

    def move_to(self, x: int, y: int) -> None:
        self._record(action="move_to", x=x, y=y)

    def scroll(self, direction: str, amount: int, x: int | None = None, y: int | None = None) -> dict:
        return self._record(action="scroll", direction=direction, amount=amount, x=x, y=y)

    def type_text(self, text: str) -> dict:
        return self._record(action="type", text=text)

    def press_key(self, key: str) -> dict:
        return self._record(action="press", key=key)

    def hotkey(self, combo: str) -> None:
        self._record(action="hotkey", combo=combo)

    def screen_size(self) -> tuple[int, int]:
        return (1920, 1080)

    def cursor_pos(self) -> tuple[int, int]:
        return (960, 540)
