"""BackendRegistry tests — no real models, uses mock backends."""

from __future__ import annotations

import pytest

from xclaw.core.backend_registry import BackendRegistry, BackendEntry


class MockBackend:
    """Minimal mock satisfying PerceptionBackend structural protocol."""

    def __init__(self, fail_load: bool = False):
        self._loaded = False
        self._fail_load = fail_load

    def load_models(self) -> None:
        if self._fail_load:
            raise RuntimeError("load failed")
        self._loaded = True

    def detect_icons(self, image, conf=0.3):
        return []

    def detect_text(self, image, min_confidence=0.6):
        return []

    def caption_icons(self, image, icon_elements):
        return []

    @property
    def caption_enabled(self) -> bool:
        return False

    @property
    def caption_conditional(self) -> bool:
        return False


class TestBackendEntry:
    def test_stats_empty(self):
        entry = BackendEntry(name="test", backend=MockBackend())
        s = entry.stats()
        assert s["name"] == "test"
        assert s["call_count"] == 0
        assert s["avg_ms"] == 0.0

    def test_record_call(self):
        entry = BackendEntry(name="test", backend=MockBackend())
        entry.record_call(100.0)
        entry.record_call(200.0)
        s = entry.stats()
        assert s["call_count"] == 2
        assert s["total_ms"] == 300.0
        assert s["avg_ms"] == 150.0

    def test_record_error(self):
        entry = BackendEntry(name="test", backend=MockBackend())
        entry.record_error()
        entry.record_error()
        assert entry.stats()["error_count"] == 2


class TestBackendRegistry:
    def test_register_and_active(self):
        reg = BackendRegistry()
        b = MockBackend()
        reg.register("mock", b)
        assert reg.active is b

    def test_first_registered_becomes_active(self):
        reg = BackendRegistry()
        b1 = MockBackend()
        b2 = MockBackend()
        reg.register("first", b1)
        reg.register("second", b2)
        assert reg.active is b1

    def test_switch(self):
        reg = BackendRegistry()
        b1 = MockBackend()
        b2 = MockBackend()
        reg.register("a", b1)
        reg.register("b", b2)
        result = reg.switch("b")
        assert result["status"] == "ok"
        assert result["active"] == "b"
        assert reg.active is b2
        # b2 should have been loaded
        assert b2._loaded

    def test_switch_nonexistent_raises(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        with pytest.raises(KeyError):
            reg.switch("nonexistent")

    def test_unregister(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        reg.register("b", MockBackend())
        reg.unregister("b")
        assert "b" not in reg.list_backends()["backends"]

    def test_unregister_active_raises(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        with pytest.raises(ValueError):
            reg.unregister("a")

    def test_unregister_nonexistent_raises(self):
        reg = BackendRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nope")

    def test_active_empty_raises(self):
        reg = BackendRegistry()
        with pytest.raises(RuntimeError):
            _ = reg.active

    def test_list_backends(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        reg.register("b", MockBackend())
        result = reg.list_backends()
        assert result["status"] == "ok"
        assert result["active"] == "a"
        assert "a" in result["backends"]
        assert "b" in result["backends"]

    def test_backend_status_active(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        result = reg.backend_status()
        assert result["status"] == "ok"
        assert result["name"] == "a"

    def test_backend_status_by_name(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        reg.register("b", MockBackend())
        result = reg.backend_status("b")
        assert result["name"] == "b"

    def test_backend_status_not_found(self):
        reg = BackendRegistry()
        reg.register("a", MockBackend())
        result = reg.backend_status("nope")
        assert result["status"] == "error"

    def test_backend_status_empty(self):
        reg = BackendRegistry()
        result = reg.backend_status()
        assert result["status"] == "error"

    def test_switch_lazy_loads(self):
        reg = BackendRegistry()
        b = MockBackend()
        reg.register("a", b)
        assert not b._loaded
        reg.switch("a")
        assert b._loaded

    def test_active_entry_tracks_stats(self):
        reg = BackendRegistry()
        b = MockBackend()
        reg.register("a", b)
        reg.switch("a")
        entry = reg.active_entry
        entry.record_call(50.0)
        entry.record_call(150.0)
        s = entry.stats()
        assert s["call_count"] == 2
        assert s["avg_ms"] == 100.0
