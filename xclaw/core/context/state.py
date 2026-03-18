"""Cross-process persistent state for the smart perception scheduler."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict

from xclaw.config import CONTEXT_STATE_PATH, CONTEXT_CACHE_TTL, CONTEXT_CRITICAL_KEYS


def parse_base_key(key: str) -> str:
    """Extract the base key from a combo key string (e.g. 'ctrl+enter' → 'enter')."""
    return key.split("+")[-1] if "+" in key else key


@dataclass
class ActionRecord:
    """A single recorded action."""

    action: str  # "click" | "type" | "press" | "scroll" | "wait"
    params: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {"action": self.action, "params": self.params, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict) -> ActionRecord:
        return cls(action=d["action"], params=d.get("params", {}), timestamp=d.get("timestamp", 0.0))


@dataclass
class ContextState:
    """Persistent state for the smart perception scheduler.

    Serialized to JSON on disk so independent CLI invocations share state.
    """

    last_screenshot_path: str | None = None
    last_result_dict: dict | None = None
    last_perception_level: str | None = None
    last_perception_time: float | None = None
    cached_elements: list[dict] = field(default_factory=list)
    cached_resolution: tuple[int, int] = (0, 0)
    action_history: list[ActionRecord] = field(default_factory=list)
    consecutive_cheap_count: int = 0
    confidence: float = 0.0

    # ── Persistence ──

    def save(self) -> None:
        """Write state to CONTEXT_STATE_PATH as JSON (atomic, error-tolerant)."""
        try:
            CONTEXT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_screenshot_path": self.last_screenshot_path,
                "last_result_dict": self.last_result_dict,
                "last_perception_level": self.last_perception_level,
                "last_perception_time": self.last_perception_time,
                "cached_elements": self.cached_elements,
                "cached_resolution": list(self.cached_resolution),
                "action_history": [a.to_dict() for a in self.action_history],
                "consecutive_cheap_count": self.consecutive_cheap_count,
                "confidence": self.confidence,
            }
            tmp = CONTEXT_STATE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp), str(CONTEXT_STATE_PATH))
        except OSError:
            pass  # 状态丢失可恢复，下次会 force full pipeline

    @classmethod
    def load(cls) -> ContextState | None:
        """Load state from disk. Returns None if file doesn't exist."""
        if not CONTEXT_STATE_PATH.exists():
            return None
        try:
            data = json.loads(CONTEXT_STATE_PATH.read_text(encoding="utf-8"))
            return cls(
                last_screenshot_path=data.get("last_screenshot_path"),
                last_result_dict=data.get("last_result_dict"),
                last_perception_level=data.get("last_perception_level"),
                last_perception_time=data.get("last_perception_time"),
                cached_elements=data.get("cached_elements", []),
                cached_resolution=tuple(data.get("cached_resolution") or [0, 0]),
                action_history=[
                    ActionRecord.from_dict(a) for a in data.get("action_history", [])
                ],
                consecutive_cheap_count=data.get("consecutive_cheap_count", 0),
                confidence=data.get("confidence", 0.0),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    # ── Mutators ──

    def record_action(self, action: str, params: dict) -> None:
        """Append an action and trim history to 10 entries."""
        self.action_history.append(
            ActionRecord(action=action, params=params, timestamp=time.time())
        )
        if len(self.action_history) > 10:
            self.action_history = self.action_history[-10:]

    def record_perception(self, level: str, result_dict: dict | None = None,
                          screenshot_path: str | None = None,
                          elements: list[dict] | None = None,
                          resolution: tuple[int, int] | None = None) -> None:
        """Update state after a perception event."""
        self.last_perception_level = level
        self.last_perception_time = time.time()
        if result_dict is not None:
            self.last_result_dict = result_dict
        if screenshot_path is not None:
            self.last_screenshot_path = screenshot_path
        if elements is not None:
            self.cached_elements = elements
        if resolution is not None:
            self.cached_resolution = resolution

        if level in ("L0", "L1"):
            self.consecutive_cheap_count += 1
        else:
            self.consecutive_cheap_count = 0

        if level in ("L2", "L3"):
            self.confidence = 1.0

    # ── Queries ──

    def is_stale(self) -> bool:
        """True if cache has expired beyond CONTEXT_CACHE_TTL."""
        if self.last_perception_time is None:
            return True
        return (time.time() - self.last_perception_time) > CONTEXT_CACHE_TTL

    def is_critical_action(self) -> bool:
        """True if the most recent action is a critical key press."""
        if not self.action_history:
            return False
        last = self.action_history[-1]
        if last.action == "press":
            key = last.params.get("key", "").lower()
            # Handle combo keys like ctrl+enter → check the base key
            base_key = parse_base_key(key)
            return base_key in CONTEXT_CRITICAL_KEYS
        return False

    def last_action(self) -> ActionRecord | None:
        """Return the most recent action, or None."""
        return self.action_history[-1] if self.action_history else None
