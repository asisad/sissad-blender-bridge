"""Install the owned opt-out-only client compatibility file without replacing config.

Run with the bridge environment, e.g. ``uv run python scripts/repair-community-status.py
--config config.local.json --profile community52``. No Blender process is touched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from sissad_blender_bridge.client import BridgeClient, BridgeError
from sissad_blender_bridge.community_bootstrap import DISABLE_FLAGS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.local.json")
    parser.add_argument("--profile", required=True)
    options = parser.parse_args()
    profile = BridgeClient(options.config).profile(options.profile)
    command = Path(profile["command"])
    if command.name.casefold() not in {"mcp-for-blender.exe", "mcp-for-blender"}:
        raise BridgeError("profile_invalid", "Select an existing Community client profile.")
    environment = {**os.environ, **profile.get("env", {})}
    if not any(environment.get(key, "").lower() in {"true", "1", "yes", "on"} for key in DISABLE_FLAGS):
        raise BridgeError("privacy_required", "An existing explicit telemetry opt-out is required; no file changed.")
    interpreter = command.with_name("python.exe" if command.suffix.casefold() == ".exe" else "python")
    probe = subprocess.run([str(interpreter), "-c",
        "import blender_mcp,json; print(json.dumps(list(blender_mcp.__path__)))"],
        env=environment, capture_output=True, text=True, timeout=20, check=True)
    paths = json.loads(probe.stdout)
    if len(paths) != 1:
        raise BridgeError("package_invalid", "Ambiguous Community package; no file changed.")
    package = Path(paths[0]).resolve()
    if package.name != "blender_mcp" or not (package / "telemetry.py").is_file():
        raise BridgeError("package_invalid", "Expected Community client package not found; no file changed.")
    import sissad_blender_bridge.community_bootstrap as bootstrap

    source = Path(bootstrap.__file__).with_name("community_disabled_config.py")
    content = source.read_bytes()
    target = package / "config.py"
    try:
        with target.open("xb") as stream:
            stream.write(content)
        changed, reason = True, "owned_opt_out_compatibility_created"
    except FileExistsError:
        changed = False
        reason = "owned_compatibility_already_present" if target.read_bytes() == content else "existing_config_preserved"
    print(json.dumps({"changed": changed, "reason": reason, "target": str(target),
        "source_sha256": hashlib.sha256(content).hexdigest()}))


if __name__ == "__main__":
    main()
