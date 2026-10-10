# Windows installation and startup

Prerequisites: Git, uv, and installed Blender executables. Run commands from the repository root. Replace example paths with real executable paths; the script validates their reported versions.

```powershell
.\scripts\setup.ps1 -Blender52 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -Blender53 'D:\Apps\Blender53\blender.exe'
```

The 5.2 executable can be discovered at its standard Program Files location. A 5.3 executable must be supplied explicitly. Only configured versions receive profiles. Setup requires Git and uv, clones missing upstream checkouts at pinned commits, creates separate Python 3.11 server environments, installs version-pinned dependencies from `requirements/`, installs the wrapper with `uv sync --frozen`, and invokes the add-on installer. Existing upstream checkouts must match the pins and be clean; they are never reset automatically. The dependency files capture the tested Windows versions; cross-platform upstream installation is not tested.

Before add-on installation, setup saves unique dated copies of existing preferences, owned add-ons and local configuration under `.runtime/backups/`. Custom Blender resource environment variables are rejected because their backup paths require inspection. The add-on installer also makes a unique backup, disables old loaded modules and reloads the installed copies. Setup may have completed earlier steps before a later failure; preserve its output and use [rollback](rollback.md).

Setup creates `config.local.json` with local absolute paths. Do not publish this file or private backups. Existing local configuration is backed up before replacement. With both versions supplied, profiles are `lab52`, `community52`, `lab53`, and `community53`. Ports are respectively 9876, 9877, 9886 and 9887, bound to loopback. This script does not itself register entries in Codex or provision a web tunnel.

## Start an owned Blender process

```powershell
.\scripts\start-blender.ps1 -BlenderPath 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -Version 52 -TestScene -Visible
uv run sissad-blender --config config.local.json doctor
uv run sissad-blender --config config.local.json tools --profile lab52
```

Omit `-Visible` for the default hidden window. Omit `-TestScene` for normal startup: only the explicit test mode uses factory startup and marks the scene as disposable. The bootstrap must accept `--test-scene` and set its test marker only for that flag. Both modes enable Blender online mode because the Lab integration requires it for its local service. This permission is not limited to loopback by Blender itself.

Startup rejects occupied ports, starts a new owned process, and writes separate stdout/stderr logs and a PID/executable/arguments record under `.runtime/`. It does not stop existing processes or reset an existing scene. The process record proves launch ownership, not connection readiness. Verify [acceptance](acceptance.md) before using production scenes. Newer and older builds need their own compatibility evidence.

Validation status of these installation scripts: syntax parsing only until an installation run is explicitly recorded. The current setup is not evidence that running these scripts on a fresh machine succeeds.
