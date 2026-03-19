"""BackendRegistry — thread-safe named registry for perception backends."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from xclaw.core.perception.backend import PerceptionBackend


@dataclass
class BackendEntry:
    name: str
    backend: PerceptionBackend
    loaded: bool = False
    call_count: int = 0
    total_ms: float = 0.0
    error_count: int = 0

    def record_call(self, elapsed_ms: float) -> None:
        self.call_count += 1
        self.total_ms += elapsed_ms

    def record_error(self) -> None:
        self.error_count += 1

    def stats(self) -> dict:
        avg_ms = round(self.total_ms / self.call_count, 1) if self.call_count else 0.0
        return {
            "name": self.name,
            "loaded": self.loaded,
            "call_count": self.call_count,
            "total_ms": round(self.total_ms, 1),
            "avg_ms": avg_ms,
            "error_count": self.error_count,
        }


class BackendRegistry:
    """Thread-safe named backend registry. Daemon holds a single instance."""

    def __init__(self):
        self._lock = threading.Lock()
        self._backends: dict[str, BackendEntry] = {}
        self._active_name: str | None = None

    def register(self, name: str, backend: PerceptionBackend) -> None:
        with self._lock:
            self._backends[name] = BackendEntry(name=name, backend=backend)
            if self._active_name is None:
                self._active_name = name

    def unregister(self, name: str) -> None:
        with self._lock:
            if name not in self._backends:
                raise KeyError(f"Backend '{name}' not registered")
            if self._active_name == name:
                raise ValueError(f"Cannot unregister active backend '{name}'")
            del self._backends[name]

    @property
    def active(self) -> PerceptionBackend:
        with self._lock:
            if self._active_name is None:
                raise RuntimeError("No backend registered")
            return self._backends[self._active_name].backend

    @property
    def active_entry(self) -> BackendEntry:
        with self._lock:
            if self._active_name is None:
                raise RuntimeError("No backend registered")
            return self._backends[self._active_name]

    def switch(self, name: str) -> dict:
        """Switch active backend (lazy-loads if needed). Returns status dict."""
        with self._lock:
            if name not in self._backends:
                raise KeyError(f"Backend '{name}' not registered")
            entry = self._backends[name]
            if not entry.loaded:
                entry.backend.load_models()
                entry.loaded = True
            self._active_name = name
            return {"status": "ok", "active": name}

    def list_backends(self) -> dict:
        with self._lock:
            return {
                "status": "ok",
                "active": self._active_name,
                "backends": {
                    name: entry.stats()
                    for name, entry in self._backends.items()
                },
            }

    def backend_status(self, name: str | None = None) -> dict:
        with self._lock:
            target = name or self._active_name
            if target is None:
                return {"status": "error", "message": "No backend registered"}
            if target not in self._backends:
                return {"status": "error", "message": f"Backend '{target}' not found"}
            return {"status": "ok", **self._backends[target].stats()}
