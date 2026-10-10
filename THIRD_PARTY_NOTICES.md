# Third-party notices and provenance

This repository coordinates upstream software installed separately. Upstream source and Blender binaries are not bundled by this documentation. Do not imply that the project's own license relicenses any upstream component or downloaded asset.

| Component | Authoritative source | License status | Distribution |
|---|---|---|---|
| Blender Lab MCP | https://projects.blender.org/lab/blender_mcp | GPL-3.0-or-later; copyright 2026 Blender Authors | Installed separately; not bundled |
| MCP for Blender | https://github.com/ahujasid/mcp-for-blender | MIT; copyright 2025 Siddharth Ahuja | Installed separately; not bundled |
| Blender | https://www.blender.org/about/license/ | Consult the official license and actual distribution | User installation; not bundled |

## Source review on 2026-10-11

- Blender Lab MCP: commit `dbbf836ad4b1025f14a2b3b504c43903f39e0b04`, server `1.0.2`, add-on `1.0.0`. License verified in root `LICENSE`, `addon/blender_mcp_addon/blender_manifest.toml` and the SPDX header in `mcp/blmcp/__init__.py`. The GPL component remains a separately installed upstream package; this project's license does not relicense it.
- MCP for Blender: commit `7a0373ec9199183cb460068c4f96aed9c579fb4f`, package `2.1.9`. License and attribution verified in root `LICENSE` and `pyproject.toml`.
- `scripts/install_addons.py` copies upstream add-ons into the user's local Blender add-ons folder. Its local community copy changes the default socket host to literal `127.0.0.1` and the default port to the selected per-version port. The pinned checkout remains unchanged. These installed copies are not included in this repository's published source; upstream headers remain in the copied source. Keep the community `LICENSE` alongside any redistribution of that copy.

If any upstream source is directly included in a published artifact, add its path, copyright attribution, applicable license text and modification notice here before commit and satisfy the upstream redistribution terms. Do not copy AGPL or unlicensed source into this runtime. Runtime dependencies must retain required notices in any redistributed artifact. Installation and static source inspection do not establish runtime compatibility; see `docs/compatibility.md` and the dated acceptance evidence.

Documentation links identify sources, not an endorsement or guarantee of compatibility. Third-party assets and generated/downloaded models can have separate licenses; record their source and usage terms with the asset.
