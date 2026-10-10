[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BlenderPath,
    [Parameter(Mandatory=$true)][ValidateSet('52','53')][string]$Version,
    [switch]$TestScene,
    [switch]$Visible
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$bridgeRoot = Split-Path -Parent $PSScriptRoot
$executable = (Resolve-Path -LiteralPath $BlenderPath).Path
$expected = if ($Version -eq '52') { '5.2' } else { '5.3' }
$reported = & $executable --version
if ($LASTEXITCODE -ne 0 -or ($reported -join "`n") -notmatch ('Blender ' + [regex]::Escape($expected) + '\.')) { throw 'Executable version does not match -Version.' }
$labPort = if ($Version -eq '52') { 9876 } else { 9886 }
$communityPort = $labPort + 1
foreach ($port in @($labPort, $communityPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw "Port $port is occupied; no existing process was stopped." }
}
foreach ($relative in @('.runtime\logs', '.runtime\processes', '.runtime\evidence')) { New-Item -ItemType Directory -Path (Join-Path $bridgeRoot $relative) -Force | Out-Null }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$arguments = @('--online-mode')
if ($TestScene) { $arguments += '--factory-startup' }
$arguments += @('--python', (Join-Path $PSScriptRoot 'start_session.py'), '--', '--root', $bridgeRoot, '--lab-port', [string]$labPort, '--community-port', [string]$communityPort)
# The bootstrap must mark only explicitly requested disposable test sessions.
if ($TestScene) { $arguments += '--test-scene' }
foreach ($argument in $arguments) { if ($argument.Contains('"')) { throw 'Embedded quotes in an argument are unsupported.' } }
$argumentLine = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
$stdout = Join-Path $bridgeRoot ".runtime\logs\blender-$Version-$stamp.stdout.log"
$stderr = Join-Path $bridgeRoot ".runtime\logs\blender-$Version-$stamp.stderr.log"
$windowStyle = if ($Visible) { 'Normal' } else { 'Hidden' }
$process = Start-Process -FilePath $executable -ArgumentList $argumentLine -WorkingDirectory $bridgeRoot -WindowStyle $windowStyle -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$record = @{ pid=$process.Id; executable=$executable; arguments=$arguments; started_utc=(Get-Date).ToUniversalTime().ToString('o'); version=$Version; test_scene=[bool]$TestScene; stdout=$stdout; stderr=$stderr; lab_port=$labPort; community_port=$communityPort }
$recordPath = Join-Path $bridgeRoot ".runtime\processes\blender-$($process.Id)-$stamp.json"
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $recordPath -Encoding UTF8
Write-Output "Started owned process $($process.Id). Record: $recordPath. Startup is not yet a verified connection."
