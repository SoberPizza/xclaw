"""LRU result cache with coordinate reverse-lookup."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from pathlib import Path

from xclaw.config import CACHE_MAX_SIZE
from xclaw.core.pipeline import PipelineResult


def _image_key(image_path: str) -> str:
    """SHA256 prefix of image file content."""
    data = Path(image_path).read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


class ResultCache:
    """LRU cache for pipeline results with coordinate reverse-lookup."""

    def __init__(self, max_size: int = CACHE_MAX_SIZE):
        self._max_size = max_size
        self._store: OrderedDict[str, PipelineResult] = OrderedDict()

    def put(self, image_path: str, result: PipelineResult) -> None:
        key = _image_key(image_path)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = result
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def get(self, image_path: str) -> PipelineResult | None:
        key = _image_key(image_path)
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def get_latest(self) -> PipelineResult | None:
        if not self._store:
            return None
        key = next(reversed(self._store))
        return self._store[key]

    def lookup_point(self, image_path: str, x: int, y: int) -> dict | None:
        """Reverse-lookup: find what element/column contains (x, y).

        Returns:
            {"element": {...}, "column": {...}} or None
        """
        result = self.get(image_path)
        if result is None:
            return None

        hit: dict = {}

        # Find element containing the point
        for elem in result.elements:
            if elem.bbox[0] <= x <= elem.bbox[2] and elem.bbox[1] <= y <= elem.bbox[3]:
                hit["element"] = {
                    "id": elem.id,
                    "type": elem.type,
                    "content": elem.content,
                    "bbox": list(elem.bbox),
                }
                break

        # Find column containing the point
        if result.columns:
            for col in result.columns:
                if col.x_start <= x <= col.x_end:
                    hit["column"] = {
                        "id": col.id,
                        "x_start": col.x_start,
                        "x_end": col.x_end,
                    }
                    break

        return hit if hit else None

    def clear(self) -> None:
        self._store.clear()


# Module-level singleton
_cache: ResultCache | None = None


def get_cache() -> ResultCache:
    """Get or create the global result cache singleton."""
    global _cache
    if _cache is None:
        _cache = ResultCache()
    return _cache
