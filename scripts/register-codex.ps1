[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$bridgeRoot = (Resolve-Path -LiteralPath $Root).Path
$bridgeConfig = Join-Path $bridgeRoot 'config.local.json'
$bridgeExecutable = Join-Path $bridgeRoot '.venv/Scripts/sissad-blender.exe'
foreach ($required in @($bridgeConfig, $bridgeExecutable)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required integration file is missing: $required"
    }
}
$codexCommand = (Get-Command codex.cmd -ErrorAction Stop).Source
$profileConfig = Get-Content -LiteralPath $bridgeConfig -Raw | ConvertFrom-Json
$configuredProfiles = @($profileConfig.profiles.PSObject.Properties.Name)
$profileNames = @($configuredProfiles)
if ($profileNames.Count -eq 0) {
    throw 'At least one Blender profile is required.'
}
foreach ($profileName in $profileNames) {
    if ($profileName -notmatch '^[A-Za-z][A-Za-z0-9_-]{0,63}$') { throw 'Profile names must be safe MCP server identifiers.' }
}

$integrationRoot = Join-Path $bridgeRoot '.runtime/codex-integration'
$marketplaceFile = Join-Path $integrationRoot '.agents/plugins/marketplace.json'
$pluginRoot = Join-Path $integrationRoot 'plugins/sissad-blender-bridge'
$pluginFile = Join-Path $pluginRoot '.codex-plugin/plugin.json'
$mcpFile = Join-Path $pluginRoot '.mcp.json'
$marketplaceName = 'sissad-blender-bridge-local'
$pluginName = 'sissad-blender-bridge'

# Never replace a directory whose existing manifests do not establish ownership.
if (Test-Path -LiteralPath $integrationRoot) {
    foreach ($owned in @(
        @{ Path = $marketplaceFile; Name = $marketplaceName },
        @{ Path = $pluginFile; Name = $pluginName }
    )) {
        if (-not (Test-Path -LiteralPath $owned.Path -PathType Leaf)) {
            throw 'Existing integration directory has missing ownership manifests; inspect it before retrying.'
        }
        $existingManifest = Get-Content -LiteralPath $owned.Path -Raw | ConvertFrom-Json
        if ($existingManifest.name -ne $owned.Name) {
            throw 'Existing integration belongs to another plugin; refusing to overwrite it.'
        }
    }
}

$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$backupRoot = Join-Path $bridgeRoot ('.runtime/backups/codex-registration-' + $stamp)
[void](New-Item -ItemType Directory -Path $backupRoot -Force)
$codexConfigDirectory = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
} else {
    $env:CODEX_HOME
}
$codexConfigFile = Join-Path $codexConfigDirectory 'config.toml'
if (Test-Path -LiteralPath $codexConfigFile -PathType Leaf) {
    Copy-Item -LiteralPath $codexConfigFile -Destination (Join-Path $backupRoot 'config.toml')
}
if (Test-Path -LiteralPath $integrationRoot) {
    Copy-Item -LiteralPath $integrationRoot -Destination (Join-Path $backupRoot 'codex-integration') -Recurse
}

$marketplace = [ordered]@{
    name = $marketplaceName
    interface = @{ displayName = 'SiSsad Blender Bridge' }
    plugins = @(@{
        name = $pluginName
        source = @{ source = 'local'; path = './plugins/sissad-blender-bridge' }
        policy = @{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
        category = 'Design'
    })
}
$plugin = [ordered]@{
    name = $pluginName
    version = '0.1.0'
    description = 'Independent local Blender Lab and community MCP integration.'
    author = @{ name = 'SiSsad' }
    repository = 'https://github.com/asisad/sissad-blender-bridge'
    license = 'MIT'
    keywords = @('blender', '3d', 'mcp', 'mcp-app')
    mcpServers = './.mcp.json'
    interface = @{
        displayName = 'SiSsad Blender Bridge'
        shortDescription = 'Connect to local Blender scenes'
        longDescription = 'Configured local profiles for Blender Lab MCP and MCP for Blender. Requires installed upstream add-ons and a running Blender session. Independent of the Blender Foundation.'
        developerName = 'SiSsad'
        category = 'Design'
        capabilities = @('Interactive', 'Read', 'Write')
    }
}
$mcpServers = [ordered]@{}
foreach ($profileName in $profileNames) {
    # The proxy forwards upstream tool metadata, including MCP Apps metadata.
    $mcpServers[$profileName] = [ordered]@{
        command = $bridgeExecutable
        args = @('--config', $bridgeConfig, 'serve', '--profile', $profileName)
        tool_timeout_sec = 600
    }
}
$documents = @(
    @{ Path = $marketplaceFile; Value = $marketplace },
    @{ Path = $pluginFile; Value = $plugin },
    @{ Path = $mcpFile; Value = @{ mcpServers = $mcpServers } }
)
foreach ($document in $documents) {
    [void](New-Item -ItemType Directory -Path (Split-Path -Parent $document.Path) -Force)
    $serialized = $document.Value | ConvertTo-Json -Depth 12
    [void]($serialized | ConvertFrom-Json)
    [System.IO.File]::WriteAllText($document.Path, $serialized, [System.Text.UTF8Encoding]::new($false))
}

& $codexCommand plugin marketplace add $integrationRoot
if ($LASTEXITCODE -ne 0) {
    throw "Codex marketplace registration failed. Backup is preserved at $backupRoot"
}
& $codexCommand plugin add "$pluginName@$marketplaceName" --json
if ($LASTEXITCODE -ne 0) {
    throw "Codex plugin installation failed. Backup is preserved at $backupRoot"
}
Write-Output 'SiSsad Blender Bridge plugin installed. Reopen the chat or restart Codex to discover its tools.'
Write-Output "Registration backup: $backupRoot"
