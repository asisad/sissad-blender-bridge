# Hidden Blender-dependent tunnel — 2026-10-23

The existing Windows recovery task now starts the supervisor with `pythonw.exe`.
The task is marked Hidden and its child commands use `CREATE_NO_WINDOW`. It keeps
the existing logon trigger, current-user principal, IgnoreNew instance policy,
spaced retries and bounded logs. It never opens Blender at logon.

Only the small background watcher starts at sign-in. The dedicated tunnel starts
when the configured Blender executable is running and both local bridge ports are
ready. Closing that Blender stops the dedicated managed runtime on the next poll
(normally ten seconds, plus any in-flight command). An open Blender with bridges
not ready is left untouched. No user scene is closed, saved or edited.

## Deployment on the existing installation

The maintained source is `scripts/supervise-blender.py`; the existing deployment
is `.runtime/service/supervisor.py`, with its unchanged private `config.json`.
Back up the task XML and deployed script privately before replacing the script.
Stop only the existing recovery task, copy the maintained source into that service
directory, then change that task's action from the environment's `python.exe` to
`pythonw.exe`. Keep its arguments and working directory pointing at the existing
service and project. Set the task's Hidden setting and start the same task again.
Do not create another task or tunnel. No administrator elevation is needed for
this existing current-user installation.

The source expects the existing service configuration, DPAPI credential file and
tunnel profile. It is not a fresh installer or a new credential flow. Preserve the
alias, tunnel ID, profile bytes and key file. Do not put private configuration in
Git. This repair does not modify add-on sources, RAG or design files.

The installed tunnel-client **v0.0.15** exposes
`runtimes stop <alias> --json`; it stops the local managed runtime, without
removing its metadata or remote tunnel. Before stopping, the supervisor verifies
the alias, tunnel ID, profile path and actual process executable. It does not
terminate a stale recorded PID or stop any Blender process.

## Verified results

- All **50 tests passed**, including the presence/readiness/retry policy.
- The updated task actually ran two windowless Python launcher/interpreter
  processes and one managed tunnel. There were no visible console/PowerShell/
  Python/tunnel windows in the returned native window inventory.
- The local runtime became healthy and ready; an actual Blender read reported
  **5.2.2 LTS**. The actual ChatGPT Web bridge returned the same process, scene,
  file, dirty state and three-object count.
- A controlled absent-presence observation exercised the exact production stop
  branch against the live dedicated runtime. It stopped, remained stopped on a
  second absent observation, then reconnected when actual presence checks resumed.
  **Blender itself remained open throughout**; no reboot or actual Blender close
  is claimed as a test.
- One supervisor instance is enforced by both the scheduled task and file lock.
  Existing retries `[15, 30, 60, 120, 300]` seconds and one-MiB logs with two
  backups remain in place. Only ready local bridge sessions are connected.

Private evidence and rollback files are under
`.runtime/evidence/hidden-lifecycle-20261023/`, excluded from public Git.
The runtime may remain in Task Manager as a background process; it has no desktop
window or taskbar button. Blender's own normal window remains visible.
