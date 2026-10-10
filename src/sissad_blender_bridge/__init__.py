"""Independent Blender MCP client. Calls may modify Blender and are never retried."""
from .client import BridgeClient, BridgeError

__all__ = ["BridgeClient", "BridgeError"]
__version__ = "0.1.0"
