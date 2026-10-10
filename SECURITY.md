# Security model

## Explicit independent-project exception

On 2026-10-11 the owner explicitly authorized arbitrary Python execution for this independent Blender project, including separately installed upstream Blender integrations. This authorization does not apply to the SketchUp repository or relax its security invariants.

Python executed inside Blender has the privileges of that Blender process. It may read/write files, access the network and invoke available process functionality. Loopback networking, a project directory, virtual environment, approval UI or upstream safe mode is not a sandbox. Do not claim risk-free execution or guaranteed geometry protection.

## Boundaries

- Bind raw add-on transports to a literal loopback address. Never expose them directly to the internet, a LAN wildcard address or router port forwarding.
- Use authenticated supported tunnelling for web access; do not create unauthenticated public forwarding.
- Keep credentials out of source, logs, tool output, issue reports, images and release artifacts. Preserve the user's existing sign-in.
- Keep upstream installations pinned and separate; review their license and security/telemetry behavior at the selected commit.
- Serialize mutations to each scene. Do not retry uncertain writes until inspecting their result.
- Use disposable scenes for acceptance, preserve unsaved user work, and maintain backups. Geometry signatures are detection, not execution isolation.
- Enable external paid services and asset providers only within authorized scope, with applicable license and credential handling.

Telemetry settings are version-specific. A configured opt-out is not proof that no network traffic occurs. Record the actual settings and checks, and avoid enabling unnecessary external services.

## Reporting

Do not post secrets or private scene files in public issues. Report a sanitized reproduction, affected build/commit and observed impact. A private security-reporting channel must be configured before promising private vulnerability intake.

Sources: [Blender Lab MCP](https://www.blender.org/lab/mcp-server/), [community integration](https://github.com/ahujasid/mcp-for-blender), [Secure MCP Tunnels](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
