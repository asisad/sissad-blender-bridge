# SiSsad Blender Bridge

1. Independent Blender integration project. Do not modify the sibling SketchUp repository.
2. The user explicitly authorized installing Blender Lab MCP and MCP for Blender, local and web connection work, parallel agents, and publication to the public asisad/sissad-blender-bridge repository on 2026-10-11.
3. Scoped exception: the user authorized Python execution through these two tools on the local Blender connection. This is not a sandbox and does not change SketchUp security rules.
4. Bind raw Blender services only to literal 127.0.0.1. Never publish raw sockets. Never commit credentials, user configuration, third-party checkouts, or private scenes.
5. One writer per Blender scene. Preserve existing files and settings; test only disposable scenes. No paid asset service activation.
6. Record exact versions, upstream commits, evidence and unresolved blockers. Do not claim all plugins or future versions are tested.
7. Run unit and integration checks, inspect actual rendered images, and sanitize publication before a release.
