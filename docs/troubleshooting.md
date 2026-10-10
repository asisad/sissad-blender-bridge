# Troubleshooting

Record the failing command/tool, sanitized error, runtime versions and last successful acceptance step before changing configuration. Use a bounded diagnose -> fix -> retest cycle. Repeating an unchanged installation is not evidence of progress.

| Symptom | Investigation and controlled recovery |
|---|---|
| MCP registered but unavailable | Verify executable paths and environment under the actual desktop client; inspect initialize/tools/list; refresh client discovery if required |
| Cannot connect to Blender | Verify correct build and enabled add-on, expected loopback address/port and owned process; inspect add-on error output |
| Port already in use | Identify owner first; use a distinct port or stop only a known process created by this integration |
| Two integrations affect one scene | Pause new mutations, inspect current scene, restore one-writer ownership and separate adapter configuration |
| API/operator failure | Check documentation for the actual Blender version, active object/mode/context and operator poll requirements |
| Timed-out mutation | Inspect scene for applied or partial changes before retrying; do not create duplicate objects blindly |
| Screenshot/render unavailable | Inspect render engine, camera and context; do not substitute an unrelated generated image |
| Geometry changes during camera test | Compare baseline snapshot, modifier/constraint dependencies and camera-dependent Geometry Nodes |
| Local works, web fails | Check real tunnel provisioning, credentials and workspace permissions; local config does not provision web |
| Version not tested | Mark UNTESTED and run isolated acceptance; do not force unsupported installation |

Never reset the user's scene, kill an unknown Blender process, disable authentication or expose a raw port to make a test pass. Keep recoverable scene/config backups and record unresolved blockers honestly.
