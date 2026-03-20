"""Tests for the stdio serve module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from xclaw.serve import _dispatch


class TestDispatch:
    @patch("xclaw.core.context.scheduler.schedule")
    def test_look_command(self, mock_schedule):
        mock_sr = MagicMock()
        mock_sr.perception = {"elements": [], "_perception": {"changed": True}}
        mock_sr.level = "L2"
        mock_sr.diff_ratio = 0.1
        mock_sr.elapsed_ms = 100
        mock_schedule.return_value = mock_sr

        result = _dispatch({"command": "look"})
        assert result["status"] == "ok"
        assert "_meta" in result
        mock_schedule.assert_called_once()

    def test_unknown_command_returns_error(self):
        result = _dispatch({"command": "frobnicate"})
        assert result["status"] == "error"
        assert "unknown command" in result["message"]

    def test_missing_command_returns_error(self):
        result = _dispatch({})
        assert result["status"] == "error"

    @patch("xclaw.core.context.scheduler.schedule")
    @patch("xclaw.action.mouse.click")
    def test_click_command(self, mock_click, mock_schedule):
        mock_click.return_value = {"status": "ok", "action": "click", "x": 10, "y": 20}
        mock_sr = MagicMock()
        mock_sr.perception = {"elements": [], "_perception": {}}
        mock_sr.level = "L2"
        mock_sr.diff_ratio = 0.05
        mock_sr.elapsed_ms = 50
        mock_schedule.return_value = mock_sr

        result = _dispatch({"command": "click", "x": 10, "y": 20})
        assert result["status"] == "ok"
        assert result["action"]["action"] == "click"
        mock_click.assert_called_once_with(10, 20, double=False)

    @patch("xclaw.core.context.scheduler.schedule")
    @patch("xclaw.action.keyboard.type_text")
    def test_type_command(self, mock_type, mock_schedule):
        mock_type.return_value = {"status": "ok", "action": "type"}
        mock_sr = MagicMock()
        mock_sr.perception = {"elements": [], "_perception": {}}
        mock_sr.level = "L2"
        mock_sr.diff_ratio = 0.0
        mock_sr.elapsed_ms = 30
        mock_schedule.return_value = mock_sr

        result = _dispatch({"command": "type", "text": "hello"})
        assert result["status"] == "ok"
        mock_type.assert_called_once_with("hello")

    @patch("xclaw.core.context.scheduler.schedule")
    @patch("xclaw.action.keyboard.press_key")
    def test_press_command(self, mock_press, mock_schedule):
        mock_press.return_value = {"status": "ok", "action": "press"}
        mock_sr = MagicMock()
        mock_sr.perception = {"elements": [], "_perception": {}}
        mock_sr.level = "L2"
        mock_sr.diff_ratio = 0.0
        mock_sr.elapsed_ms = 30
        mock_schedule.return_value = mock_sr

        result = _dispatch({"command": "press", "key": "enter"})
        assert result["status"] == "ok"
        mock_press.assert_called_once_with("enter")
