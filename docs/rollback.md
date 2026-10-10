# Rollback

Plan rollback before installation. Record an ownership manifest of created files, environment directories, MCP entry names, add-ons and server/tunnel process identifiers. Save previous configuration and add-on files when replacing existing content. Backups can contain private settings and must remain outside public version control.

1. Finish or cancel owned work safely; save disposable test results separately. Do not close an unsaved user scene.
2. Stop only servers/tunnel clients started and owned by this installation. Identify PID and executable before stopping anything.
3. Remove only the MCP registrations created by this installation, or restore their previous exact values. Preserve unrelated entries and the existing sign-in.
4. Disable/remove only newly installed add-ons in the corresponding Blender version; restore replaced add-on files and settings from the recorded backup where applicable.
5. Restore modified configuration carefully, preserving unrelated changes made since the backup. Never overwrite the whole configuration blindly.
6. Remove owned virtual environments and generated files only after validating resolved absolute paths against the installation manifest. Preserve requested scenes and evidence.
7. Revoke an installation-specific tunnel/runtime credential if it is no longer required, without affecting shared credentials or connections.
8. Verify prior MCP entries, Blender startup and retained scene files; record checks and unresolved issues.

Undo is not a backup. Removing a bridge cannot automatically reverse arbitrary Python side effects. Source control does not capture all .blend or external asset changes; retain deliberate file backups.
