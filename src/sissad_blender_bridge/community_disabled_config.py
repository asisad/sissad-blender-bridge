"""SiSsad compatibility file for the missing Community client telemetry config.

May be copied as ``blender_mcp/config.py`` only when that client file is absent.
It has no endpoint, credential, network sender, or consent override. Refuse to
substitute for the missing upstream configuration without explicit opt-out.
"""
import os
from types import SimpleNamespace


if not any(os.environ.get(key, "").lower() in {"true", "1", "yes", "on"} for key in (
    "DISABLE_TELEMETRY", "BLENDER_MCP_DISABLE_TELEMETRY", "MCP_DISABLE_TELEMETRY"
)):
    raise ModuleNotFoundError(
        "Missing upstream telemetry config; SiSsad compatibility requires an existing explicit telemetry opt-out",
        name="blender_mcp.config",
    )

telemetry_config = SimpleNamespace(enabled=False)
