"""Machine-readable command line interface; transport diagnostics omit secrets.

The `ok` flag reflects MCP isError, not semantic verification of Blender changes.
Some upstream tools report failures only in text while leaving isError false.
Consumers must inspect returned content and verify the expected scene state.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from .client import BridgeClient, BridgeError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sissad-blender")
    parser.add_argument("--config", default="config.local.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("profiles")
    commands.add_parser("doctor")
    for action in ("tools", "call", "serve"):
        sub = commands.add_parser(action)
        sub.add_argument("--profile", required=True)
        sub.add_argument("--timeout", type=float, default=300)
        if action == "call":
            sub.add_argument("--tool", required=True)
            group = sub.add_mutually_exclusive_group()
            group.add_argument("--arguments", default="{}")
            group.add_argument("--arguments-file", type=Path)
            sub.add_argument("--output-dir", type=Path)
    options = parser.parse_args(argv)
    try:
        client = BridgeClient(options.config)
        if options.command == "serve":
            from .server import serve
            asyncio.run(serve(client, options.profile, timeout=options.timeout))
            return 0
        if options.command == "profiles":
            result = {"profiles": sorted(client.profiles)}
        elif options.command == "doctor":
            result = client.doctor()
        elif options.command == "tools":
            result = asyncio.run(client.list_tools(options.profile, timeout=options.timeout))
        else:
            try:
                text = options.arguments_file.read_text(encoding="utf-8-sig") if options.arguments_file else options.arguments
                arguments = json.loads(text)
            except (ValueError, OSError):
                raise BridgeError("arguments_invalid", "Cannot read a valid JSON arguments object.") from None
            result = asyncio.run(client.call_tool(options.profile, options.tool, arguments, output_dir=options.output_dir, timeout=options.timeout))
        ok = not result.get("isError", False)
        if options.command == "doctor":
            ok = all(p["command_found"] for p in result["profiles"].values())
        print(json.dumps({"ok": ok, "result": result}, ensure_ascii=True))
        return 0 if ok else 1
    except BridgeError as error:
        print(json.dumps({"ok": False, "error": {"code": error.code, "message": str(error)}}), file=sys.stderr if options.command == "serve" else sys.stdout)
        return 1
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "error": {"code": "local_error", "message": "Local file or configuration operation failed."}}), file=sys.stderr if options.command == "serve" else sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
