"""Action backend interface contract tests — no real mouse/keyboard events."""

from __future__ import annotations

import platform
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# ActionBackend protocol conformance
# ---------------------------------------------------------------------------


class TestActionBackendProtocol:
    def test_dry_run_satisfies_protocol(self):
        from xclaw.action.backend import ActionBackend
        from xclaw.action.dry_run_backend import DryRunBackend

        backend = DryRunBackend()
        assert isinstance(backend, ActionBackend)

    def test_dry_run_click_records(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        result = b.click(100, 200)
        assert result["status"] == "ok"
        assert result["action"] == "click"
        assert result["x"] == 100
        assert result["y"] == 200
        assert len(b.log) == 1

    def test_dry_run_double_click_records(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        result = b.double_click(300, 400)
        assert result["action"] == "double_click"
        assert len(b.log) == 1

    def test_dry_run_type_records(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        result = b.type_text("hello")
        assert result["action"] == "type"
        assert result["text"] == "hello"

    def test_dry_run_press_records(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        result = b.press_key("enter")
        assert result["action"] == "press"
        assert result["key"] == "enter"

    def test_dry_run_scroll_records(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        result = b.scroll("down", 3, 100, 200)
        assert result["action"] == "scroll"
        assert result["direction"] == "down"
        assert result["amount"] == 3

    def test_dry_run_screen_size(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        w, h = b.screen_size()
        assert w == 1920
        assert h == 1080

    def test_dry_run_cursor_pos(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        x, y = b.cursor_pos()
        assert x == 960
        assert y == 540

    def test_dry_run_move_to(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        b.move_to(50, 60)
        assert b.log[-1]["action"] == "move_to"

    def test_dry_run_hotkey(self):
        from xclaw.action.dry_run_backend import DryRunBackend

        b = DryRunBackend()
        b.hotkey("cmd+c")
        assert b.log[-1]["action"] == "hotkey"
        assert b.log[-1]["combo"] == "cmd+c"


# ---------------------------------------------------------------------------
# set_backend / get_backend
# ---------------------------------------------------------------------------


class TestBackendSingleton:
    def test_set_backend_and_use(self):
        from xclaw.action import set_backend, get_backend
        from xclaw.action.dry_run_backend import DryRunBackend

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = get_backend().click(10, 20)
            assert result["status"] == "ok"
            assert len(dry.log) == 1
        finally:
            set_backend(None)

    def test_module_level_click_delegates(self):
        from xclaw.action import set_backend, click
        from xclaw.action.dry_run_backend import DryRunBackend

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = click(50, 60)
            assert result["status"] == "ok"
            assert dry.log[-1]["x"] == 50
        finally:
            set_backend(None)

    def test_module_level_type_text_delegates(self):
        from xclaw.action import set_backend, type_text
        from xclaw.action.dry_run_backend import DryRunBackend

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = type_text("hi")
            assert result["status"] == "ok"
            assert dry.log[-1]["text"] == "hi"
        finally:
            set_backend(None)


# ---------------------------------------------------------------------------
# mouse.py high-level API
# ---------------------------------------------------------------------------


class TestMouseAPI:
    def test_click_returns_dict(self):
        from xclaw.action import set_backend
        from xclaw.action.dry_run_backend import DryRunBackend
        from xclaw.action.mouse import click

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = click(100, 200, double=False)
            assert result["status"] == "ok"
            assert result["action"] == "click"
            assert result["x"] == 100
        finally:
            set_backend(None)

    def test_double_click_returns_dict(self):
        from xclaw.action import set_backend
        from xclaw.action.dry_run_backend import DryRunBackend
        from xclaw.action.mouse import click

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = click(300, 400, double=True)
            assert result["action"] == "double_click"
        finally:
            set_backend(None)

    def test_scroll_returns_dict(self):
        from xclaw.action import set_backend
        from xclaw.action.dry_run_backend import DryRunBackend
        from xclaw.action.mouse import scroll

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = scroll("down", 3, 500, 500)
            assert result["status"] == "ok"
            assert result["action"] == "scroll"
            assert result["direction"] == "down"
            assert result["amount"] == 3
        finally:
            set_backend(None)


# ---------------------------------------------------------------------------
# keyboard.py high-level API
# ---------------------------------------------------------------------------


class TestKeyboardAPI:
    def test_type_text_returns_dict(self):
        from xclaw.action import set_backend
        from xclaw.action.dry_run_backend import DryRunBackend
        from xclaw.action.keyboard import type_text

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = type_text("Hello World")
            assert result["status"] == "ok"
            assert result["action"] == "type"
            assert result["text"] == "Hello World"
        finally:
            set_backend(None)

    def test_press_key_returns_dict(self):
        from xclaw.action import set_backend
        from xclaw.action.dry_run_backend import DryRunBackend
        from xclaw.action.keyboard import press_key

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = press_key("enter")
            assert result["status"] == "ok"
            assert result["action"] == "press"
            assert result["key"] == "enter"
        finally:
            set_backend(None)

    def test_press_combo_returns_dict(self):
        from xclaw.action import set_backend
        from xclaw.action.dry_run_backend import DryRunBackend
        from xclaw.action.keyboard import press_key

        dry = DryRunBackend()
        set_backend(dry)
        try:
            result = press_key("cmd+c")
            assert result["key"] == "cmd+c"
        finally:
            set_backend(None)


# ---------------------------------------------------------------------------
# HumanizeStrategy protocol conformance
# ---------------------------------------------------------------------------


class TestHumanizeStrategy:
    def test_noop_satisfies_protocol(self):
        from xclaw.action.humanize_strategy import HumanizeStrategy, NoopStrategy

        s = NoopStrategy()
        assert isinstance(s, HumanizeStrategy)

    def test_bezier_satisfies_protocol(self):
        from xclaw.action.humanize_strategy import HumanizeStrategy, BezierStrategy

        s = BezierStrategy()
        assert isinstance(s, HumanizeStrategy)

    def test_noop_move_calls_fn_directly(self):
        from xclaw.action.humanize_strategy import NoopStrategy

        s = NoopStrategy()
        calls = []
        fx, fy = s.move_to_target(100, 200, lambda x, y: calls.append((x, y)))
        assert fx == 100
        assert fy == 200
        assert calls == [(100, 200)]

    def test_noop_scroll_chunk_returns_all(self):
        from xclaw.action.humanize_strategy import NoopStrategy

        s = NoopStrategy()
        assert s.scroll_chunk(10) == 10

    def test_bezier_scroll_chunk_returns_subset(self):
        from xclaw.action.humanize_strategy import BezierStrategy

        s = BezierStrategy()
        chunk = s.scroll_chunk(100)
        assert 1 <= chunk <= 100


# ---------------------------------------------------------------------------
# Darwin backend (only tested on macOS)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestDarwinKeyboard:
    def test_mac_kc_has_common_keys(self):
        from xclaw.action.keyboard_darwin import MAC_KC

        for key in ["a", "z", "0", "9", "return", "tab", "space", "escape"]:
            assert key in MAC_KC, f"Missing key: {key}"

    def test_mac_mod_kc_has_modifiers(self):
        from xclaw.action.keyboard_darwin import MAC_MOD_KC

        for mod in ["cmd", "shift", "alt", "ctrl"]:
            assert mod in MAC_MOD_KC, f"Missing modifier: {mod}"

    def test_shift_chars_complete(self):
        from xclaw.action.keyboard_darwin import SHIFT_CHARS

        for char in "!@#$%^&*()_+{}|:\"<>?~":
            assert char in SHIFT_CHARS, f"Missing shift char: {char}"


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestDarwinMouse:
    def test_screen_size_returns_tuple(self):
        from xclaw.action.mouse_darwin import _screen_size

        w, h = _screen_size()
        assert isinstance(w, int) and w > 0
        assert isinstance(h, int) and h > 0

    def test_cursor_pos_returns_tuple(self):
        from xclaw.action.mouse_darwin import _cursor_pos

        x, y = _cursor_pos()
        assert isinstance(x, int)
        assert isinstance(y, int)


# ---------------------------------------------------------------------------
# Windows backend (structure-only, runs on any platform via mock)
# ---------------------------------------------------------------------------


class TestWin32KeyboardStructure:
    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_win_vk_has_common_keys(self):
        from xclaw.action.keyboard_win32 import WIN_VK

        for key in ["a", "z", "0", "9", "return", "tab", "space", "escape"]:
            assert key in WIN_VK

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_win_mod_vk_has_modifiers(self):
        from xclaw.action.keyboard_win32 import WIN_MOD_VK

        for mod in ["ctrl", "shift", "alt"]:
            assert mod in WIN_MOD_VK


# ---------------------------------------------------------------------------
# humanize.py
# ---------------------------------------------------------------------------


class TestHumanize:
    def test_bezier_point_endpoints(self):
        from xclaw.action.humanize import bezier_point

        p0, p1, p2, p3 = (0, 0), (10, 10), (20, 20), (30, 30)

        # t=0 → start
        x, y = bezier_point(0.0, p0, p1, p2, p3)
        assert abs(x - p0[0]) < 1e-6
        assert abs(y - p0[1]) < 1e-6

        # t=1 → end
        x, y = bezier_point(1.0, p0, p1, p2, p3)
        assert abs(x - p3[0]) < 1e-6
        assert abs(y - p3[1]) < 1e-6

    def test_bezier_point_midpoint(self):
        from xclaw.action.humanize import bezier_point

        # Straight line control points → midpoint should be near (15, 15)
        p0, p3 = (0, 0), (30, 30)
        p1, p2 = (10, 10), (20, 20)

        x, y = bezier_point(0.5, p0, p1, p2, p3)
        assert 10 < x < 20
        assert 10 < y < 20
