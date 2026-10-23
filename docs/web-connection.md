# ChatGPT Web connection

Reference-install status: **WEB_CONNECTED_TESTED** with the Lab 5.2 profile on
2026-10-11; see [the verification log](verification-2026-10-11.md). Every new
installation requires its own account-specific provisioning and live test.

## Prerequisites

- A locally working MCP server and Blender integration.
- A real Secure MCP Tunnel identifier provisioned for the account.
- A valid runtime API key for the tunnel client, stored outside this repository.
- Required Platform permissions and ChatGPT workspace permission to create/use the custom connection.
- A tunnel-client installation configured according to current official documentation.

Existing ChatGPT sign-in should be preserved. A tunnel runtime credential is a separate requirement; never invent a tunnel identifier, key or workspace entitlement. Local Codex configuration is not automatically a ChatGPT Web connection.

## Procedure

1. Verify local acceptance first and record the working server command and transport.
2. Check account/workspace eligibility and provision the actual tunnel using the official workflow.
3. Store the runtime key in an appropriate secret store or process environment. Do not print it, place it in command history, commit it, or include it in screenshots.
4. Connect the tunnel client to the tested local MCP server using the current documented transport. Keep Blender's raw add-on socket bound to loopback; do not publish it or forward a router port.
5. Create the custom ChatGPT connection using the real tunnel identity and authorized account settings.
6. Confirm tools appear in the target web conversation. Run a scene read and disposable test-object creation there, then verify the resulting Blender scene and image.
7. Record WEB_CONNECTED_TESTED only for successful evidence from that conversation. Otherwise record the exact missing permission, credential provisioning step or failed test; preserve working local connectivity.

Do not use an unauthenticated public tunnel as a workaround. Streamable HTTP support is transport support, not proof of video streaming. Avoid embedding version-sensitive tunnel commands here until the installed client version and current documented syntax have been verified.

## Tested Windows client procedure

The installed `tunnel-client` version used for this procedure is `0.0.15`.
Create a dedicated Platform key with only **Tunnels Read and Use**; other scopes
are not needed for attaching an already provisioned tunnel. The ChatGPT plugin's
authentication selection is **No authentication** at the MCP application layer;
the tunnel still authenticates the runtime and restricts the allowed workspace.

Use `scripts/connect-web.ps1 -TunnelClient '<path to tunnel-client.exe>'
-TunnelId '<your actual tunnel ID>' -Profile lab52` with the key already set in
the process environment as `CONTROL_PLANE_API_KEY`. Do not type the key into a
command line, chat, repository or screenshot. Alternatively pass `-RuntimeKeyFile`
pointing to a Windows DPAPI-encrypted value produced by `ConvertFrom-SecureString`
under the same Windows account. Keep that file outside the repository with a
user-only ACL. The script restores its caller's environment after launching the
managed runtime. The runtime retains the key in its own process environment.

The script uses forward slashes in quoted Windows paths because the client's
command parser interprets backslashes as shell escapes. It checks actual healthy
and ready fields, not only an exit code. The client allocates a loopback health
port for the managed runtime. No router forwarding or raw Blender exposure is used.

In ChatGPT: Plugins -> Add -> Add custom MCP server -> Tunnel, choose the dedicated
tunnel, name it, select No authentication, acknowledge the custom-server notice,
then Create as a plugin and Connect. Use Try in chat and perform the guarded test
in the acceptance document. Record the real invocation separately from Connected.

This connection targets one explicit profile. Switching to another version or
provider requires reconnecting with the corresponding profile and verifying the
actual scene version. Do not run multiple different upstreams on one tunnel ID
simultaneously. Managed runtime persistence does not by itself install Windows
startup scheduling. For an existing Windows installation with the recovery task,
use the [hidden Blender-dependent lifecycle](hidden-lifecycle-2026-10-23.md): only
the watcher starts at sign-in, and the tunnel follows Blender's running state.
Without that task, rerun the connection script with the existing local key.

Sources: [Secure MCP Tunnels](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), [connect a custom ChatGPT integration](https://developers.openai.com/plugins/deploy/connect-chatgpt), [Developer mode and MCP apps](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).
