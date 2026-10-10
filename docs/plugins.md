# Plug-in and capability inventory

Installing the bridge does not install every Blender extension or establish professional mastery of every tool. Inventory and test capabilities needed for a workflow before using them on production assets.

For each Blender installation record: build, enabled and disabled add-ons/extensions, module or extension identifier, version, source, license, manifest compatibility, dependencies, operator context requirements and tested capabilities. Distinguish installed, enabled, discoverable and tested. Never dump preference values or tokens into an inventory report.

## Workflow groups

| Workflow | Candidate capability checks |
|---|---|
| Interior/architecture | Units, dimensions, protected geometry, materials, lighting, camera views, asset provenance |
| Jewelry | Accurate scale, solid geometry, normals, thickness/manifold checks and export tolerances |
| Avatar | Rig, armature, skinning, pose, animation, texture paths and target export |
| Game environment | Mesh budget, UVs, materials, collision/LOD conventions and target-engine import |

The official Blender Lab integration and community MCP for Blender are separate upstream projects, not interchangeable packages. Install reviewed pinned versions in separate environments and use distinct server names/ports. External asset and generative services may require accounts, paid usage and additional licenses; they are not prerequisites for base connectivity and must not be enabled implicitly.

The same add-on may behave differently between Blender builds. Record tested feature support per build rather than promising all-version support. Live scene mutations remain serialized even when documentation or inventory analysis uses parallel agents.

Sources: [official integration](https://projects.blender.org/lab/blender_mcp), [community integration](https://github.com/ahujasid/mcp-for-blender), [Blender extensions](https://extensions.blender.org/).

## Discover installed capabilities

```powershell
uv run python scripts/inventory_blender.py --profile lab52 --output .runtime/evidence/inventory-lab52.json
uv run python scripts/inventory_blender.py --profile lab53 --output .runtime/evidence/inventory-lab53.json
uv run python scripts/watch_scene.py --profile lab52 --count 30 --interval 1
```

Inventory uses the Lab connection because Community Safe Mode can reject imports
needed for add-on discovery. It reads module metadata and operator names, not
preference values. Inventory files can reveal installed software and local paths;
keep them private by default. The watcher emits JSON only when its sampled object
transforms, selection or timeline change. It is bounded polling, not video or a
lossless event stream; transient changes between samples may be missed.
