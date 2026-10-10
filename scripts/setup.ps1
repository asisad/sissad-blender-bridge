[CmdletBinding()]
param([string]$Blender52, [string]$Blender53)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$bridgeRoot = Split-Path -Parent $PSScriptRoot
function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}
$uv = (Get-Command uv -ErrorAction Stop).Source
$git = (Get-Command git -ErrorAction Stop).Source
if (-not $Blender52) {
    $candidate = Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $Blender52 = $candidate }
}
if (-not $Blender52 -and -not $Blender53) { throw 'Supply -Blender52 or -Blender53 with an installed executable path.' }
if ($env:BLENDER_USER_RESOURCES -or $env:BLENDER_USER_CONFIG -or $env:BLENDER_USER_SCRIPTS) { throw 'Custom Blender resource environment detected; inspect and back up those paths before using this default installer.' }
$versions = @()
foreach ($entry in @(@{ Path=$Blender52; Version='5.2'; Suffix='52'; Lab=9876; Community=9877 }, @{ Path=$Blender53; Version='5.3'; Suffix='53'; Lab=9886; Community=9887 })) {
    if (-not $entry.Path) { continue }
    $entry.Path = (Resolve-Path -LiteralPath $entry.Path).Path
    $reported = & $entry.Path --version
    if ($LASTEXITCODE -ne 0 -or ($reported -join "`n") -notmatch ('Blender ' + [regex]::Escape($entry.Version) + '\.')) { throw "Wrong Blender version for $($entry.Path)" }
    $versions += $entry
}
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$backupRoot = Join-Path $bridgeRoot ".runtime\backups\setup-$stamp"
foreach ($dir in @('.runtime\upstream', '.runtime\venvs', '.runtime\evidence', '.runtime\logs')) { New-Item -ItemType Directory -Path (Join-Path $bridgeRoot $dir) -Force | Out-Null }
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
foreach ($entry in $versions) {
    $userRoot = Join-Path $env:APPDATA "Blender Foundation\Blender\$($entry.Version)"
    $savedRoot = Join-Path $backupRoot $entry.Version
    foreach ($relative in @('config\userpref.blend', 'scripts\addons\blender_mcp_addon', 'scripts\addons\blender_mcp.py')) {
        $source = Join-Path $userRoot $relative
        if (Test-Path -LiteralPath $source) {
            $destination = Join-Path $savedRoot $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $destination -Recurse
        }
    }
}
$configPath = Join-Path $bridgeRoot 'config.local.json'
if (Test-Path -LiteralPath $configPath) { Copy-Item -LiteralPath $configPath -Destination (Join-Path $backupRoot 'config.local.json') }
$upstreams = @(
    @{ Name='lab'; Url='https://projects.blender.org/lab/blender_mcp.git'; Commit='dbbf836ad4b1025f14a2b3b504c43903f39e0b04'; Package='mcp' },
    @{ Name='community'; Url='https://github.com/ahujasid/mcp-for-blender.git'; Commit='7a0373ec9199183cb460068c4f96aed9c579fb4f'; Package='' }
)
foreach ($item in $upstreams) {
    $checkout = Join-Path $bridgeRoot ".runtime\upstream\$($item.Name)"
    if (-not (Test-Path -LiteralPath $checkout)) {
        Invoke-Checked $git @('clone', $item.Url, $checkout)
        Invoke-Checked $git @('-C', $checkout, 'checkout', '--detach', $item.Commit)
    } else {
        $head = & $git -C $checkout rev-parse HEAD
        if ($LASTEXITCODE -ne 0 -or $head -ne $item.Commit) { throw "Existing $($item.Name) checkout differs from the pin; inspect it. No reset was performed." }
        $dirty = & $git -C $checkout status --porcelain
        if ($LASTEXITCODE -ne 0 -or $dirty) { throw "Existing $($item.Name) checkout has changes; refusing to package it." }
    }
    $venv = Join-Path $bridgeRoot ".runtime\venvs\$($item.Name)"
    $python = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { Invoke-Checked $uv @('venv', '--python', '3.11', $venv) }
    $package = if ($item.Package) { Join-Path $checkout $item.Package } else { $checkout }
    Invoke-Checked $uv @('pip', 'sync', '--python', $python, (Join-Path $bridgeRoot "requirements\$($item.Name)-lock.txt"))
    Invoke-Checked $uv @('pip', 'install', '--no-deps', '--python', $python, $package)
    & $uv pip freeze --python $python | Set-Content -LiteralPath (Join-Path $bridgeRoot ".runtime\evidence\$($item.Name)-installed.txt") -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw 'Could not record installed dependencies.' }
}
Push-Location $bridgeRoot
try { Invoke-Checked $uv @('sync', '--frozen') } finally { Pop-Location }
$profiles = [ordered]@{}
foreach ($entry in $versions) {
    # Each installation saves a separate backup before replacing these add-ons.
    Invoke-Checked $entry.Path @('--background', '--python-exit-code', '1', '--python', (Join-Path $PSScriptRoot 'install_addons.py'), '--', '--root', $bridgeRoot, '--lab-port', [string]$entry.Lab, '--community-port', [string]$entry.Community)
    $profiles["lab$($entry.Suffix)"] = @{ command=(Join-Path $bridgeRoot '.runtime\venvs\lab\Scripts\blender-mcp.exe'); args=@(); env=@{ BLENDER_MCP_HOST='127.0.0.1'; BLENDER_MCP_PORT=[string]$entry.Lab; BLENDER_PATH=$entry.Path } }
    $profiles["community$($entry.Suffix)"] = @{ command=(Join-Path $bridgeRoot '.runtime\venvs\community\Scripts\mcp-for-blender.exe'); args=@(); env=@{ BLENDER_HOST='127.0.0.1'; BLENDER_PORT=[string]$entry.Community; DISABLE_TELEMETRY='true'; BLENDER_MCP_DISABLE_TELEMETRY='true'; BLENDER_MCP_SAFE_MODE='1'; BLENDER_MCP_APPS='1'; BLENDER_MCP_OPENAI_FORMS='1' } }
}
@{ profiles=$profiles } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8
Write-Output "Setup finished. Backup: $backupRoot. Run acceptance checks before claiming connectivity."
