"""Tests for LRU result cache and coordinate reverse-lookup."""

import tempfile
import os

from xclaw.core.perception.types import RawElement
from xclaw.core.spatial.types import Region
from xclaw.core.semantic.types import Component, ComponentType
from xclaw.core.pipeline import PipelineResult
from xclaw.core.cache import ResultCache


def _make_temp_image(content: bytes = b"PNG_FAKE_DATA") -> str:
    fd, path = tempfile.mkstemp(suffix=".png")
    os.write(fd, content)
    os.close(fd)
    return path


def _make_result(elements=None, regions=None, components=None):
    return PipelineResult(
        elements=elements or [],
        resolution=(1920, 1080),
        image_path="test.png",
        regions=regions,
        components=components,
    )


class TestResultCache:
    def test_put_and_get(self):
        cache = ResultCache(max_size=4)
        path = _make_temp_image()
        result = _make_result()
        cache.put(path, result)
        assert cache.get(path) is result
        os.unlink(path)

    def test_miss(self):
        cache = ResultCache(max_size=4)
        path = _make_temp_image()
        assert cache.get(path) is None
        os.unlink(path)

    def test_lru_eviction(self):
        cache = ResultCache(max_size=2)
        paths = [_make_temp_image(f"data{i}".encode()) for i in range(3)]
        results = [_make_result() for _ in range(3)]

        cache.put(paths[0], results[0])
        cache.put(paths[1], results[1])
        cache.put(paths[2], results[2])  # should evict paths[0]

        assert cache.get(paths[0]) is None
        assert cache.get(paths[1]) is results[1]
        assert cache.get(paths[2]) is results[2]

        for p in paths:
            os.unlink(p)

    def test_get_latest(self):
        cache = ResultCache(max_size=4)
        path1 = _make_temp_image(b"img1")
        path2 = _make_temp_image(b"img2")
        r1 = _make_result()
        r2 = _make_result()

        cache.put(path1, r1)
        cache.put(path2, r2)
        assert cache.get_latest() is r2

        os.unlink(path1)
        os.unlink(path2)

    def test_clear(self):
        cache = ResultCache(max_size=4)
        path = _make_temp_image()
        cache.put(path, _make_result())
        cache.clear()
        assert cache.get(path) is None
        assert cache.get_latest() is None
        os.unlink(path)


class TestLookupPoint:
    def test_finds_element(self):
        cache = ResultCache()
        path = _make_temp_image()
        elem = RawElement(
            id=0, type="text", bbox=(100, 100, 200, 200),
            center=(150, 150), content="hello",
        )
        result = _make_result(elements=[elem])
        cache.put(path, result)

        hit = cache.lookup_point(path, 150, 150)
        assert hit is not None
        assert hit["element"]["id"] == 0
        assert hit["element"]["content"] == "hello"
        os.unlink(path)

    def test_misses_outside(self):
        cache = ResultCache()
        path = _make_temp_image()
        elem = RawElement(
            id=0, type="text", bbox=(100, 100, 200, 200),
            center=(150, 150), content="hello",
        )
        result = _make_result(elements=[elem])
        cache.put(path, result)

        hit = cache.lookup_point(path, 50, 50)
        assert hit is None
        os.unlink(path)

    def test_finds_component_and_region(self):
        cache = ResultCache()
        path = _make_temp_image()
        elem = RawElement(
            id=0, type="text", bbox=(100, 100, 200, 200),
            center=(150, 150), content="test",
        )
        comp = Component(
            id=0, type=ComponentType.CARD,
            bbox=(50, 50, 250, 250), element_ids=[0],
        )
        region = Region(
            id=0, role="main",
            bbox=(0, 0, 500, 500), block_ids=[0],
        )
        result = _make_result(elements=[elem], regions=[region], components=[comp])
        cache.put(path, result)

        hit = cache.lookup_point(path, 150, 150)
        assert "element" in hit
        assert "component" in hit
        assert hit["component"]["type"] == "card"
        assert "region" in hit
        assert hit["region"]["role"] == "main"
        os.unlink(path)
