"""Launch the unchanged Community client with its explicit telemetry opt-out.

The pinned distribution omits ``blender_mcp.config`` but imports it before
checking its telemetry-disable environment flags. Supply only ``enabled=False``
when the user already opted out; do not invent an endpoint, key, or consent.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType, SimpleNamespace


DISABLE_FLAGS = ("DISABLE_TELEMETRY", "BLENDER_MCP_DISABLE_TELEMETRY", "MCP_DISABLE_TELEMETRY")


def install_disabled_telemetry_config() -> bool:
    """Fill only a missing upstream config, only for an existing explicit opt-out."""
    if not any(os.environ.get(key, "").lower() in {"true", "1", "yes", "on"} for key in DISABLE_FLAGS):
        return False
    name = "blender_mcp.config"
    if name in sys.modules or importlib.util.find_spec(name) is not None:
        return False
    config = ModuleType(name)
    config.telemetry_config = SimpleNamespace(enabled=False)
    sys.modules[name] = config
    return True


def main():
    install_disabled_telemetry_config()
    from blender_mcp.server import main as upstream_main

    upstream_main()


if __name__ == "__main__":
    main()
