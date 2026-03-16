"""Plugin registry — singleton for managing site plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclaw.plugins.base import SitePlugin


class PluginRegistry:
    """Singleton registry for site plugins."""

    _instance: PluginRegistry | None = None

    def __init__(self):
        self._plugins: list[SitePlugin] = []

    @classmethod
    def _get_instance(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = PluginRegistry()
        return cls._instance

    def register(self, plugin: SitePlugin) -> None:
        """Register a plugin instance."""
        self._plugins.append(plugin)

    def get_active(self, url: str = "", domain: str = "") -> SitePlugin | None:
        """Return the first plugin that matches the given URL/domain, or None."""
        for plugin in self._plugins:
            if plugin.match(url=url, domain=domain):
                return plugin
        return None

    def discover(self, package_path: str = "") -> None:
        """Auto-discover plugins from a package path. (Not implemented yet.)"""
        pass

    def clear(self) -> None:
        """Remove all registered plugins."""
        self._plugins.clear()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton."""
    return PluginRegistry._get_instance()
