[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$TunnelClient,
    [Parameter(Mandatory=$true)][ValidatePattern('^tunnel_[a-zA-Z0-9]+$')][string]$TunnelId,
    [ValidatePattern('^[A-Za-z][A-Za-z0-9_-]{0,63}$')][string]$Profile='lab52',
    [string]$RuntimeKeyFile
)
$ErrorActionPreference='Stop'
$bridgeRoot=Split-Path -Parent $PSScriptRoot
$client=(Resolve-Path -LiteralPath $TunnelClient).Path
$bridge=(Resolve-Path -LiteralPath (Join-Path $bridgeRoot '.venv\Scripts\sissad-blender.exe')).Path
$config=(Resolve-Path -LiteralPath (Join-Path $bridgeRoot 'config.local.json')).Path
$profileNames = @((Get-Content -LiteralPath $config -Raw | ConvertFrom-Json).profiles.PSObject.Properties.Name)
if ($Profile -notin $profileNames) { throw 'The requested profile does not exist in config.local.json.' }
# tunnel-client parses this string with shell-style escapes, including on Windows.
$command='"'+$bridge.Replace('\','/')+'" --config "'+$config.Replace('\','/')+'" serve --profile '+$Profile
$alias='sissad-blender-'+$Profile
# Explicit existing tunnel only; do not create or repurpose an unrelated tunnel.
$previousKey = $env:CONTROL_PLANE_API_KEY
try {
    if ($RuntimeKeyFile) {
        # Windows DPAPI: decryptable only by the same Windows account on this device.
        $secureKey = (Get-Content -LiteralPath $RuntimeKeyFile -Raw).Trim() | ConvertTo-SecureString
        $env:CONTROL_PLANE_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
    }
    if (-not $env:CONTROL_PLANE_API_KEY) { throw 'Provide a dedicated runtime key in CONTROL_PLANE_API_KEY or a DPAPI RuntimeKeyFile. Never paste it into chat or commit it.' }
    $connection = & $client runtimes connect --alias $alias --profile $alias --tunnel-id $TunnelId --runtime-api-key 'env:CONTROL_PLANE_API_KEY' --mcp-command $command --json
    if ($LASTEXITCODE -ne 0) { throw 'Tunnel runtime failed to connect. Inspect the dedicated runtime log locally.' }
    $status = $null
    for ($attempt=0; $attempt -lt 15; $attempt++) {
        $statusJson = & $client runtimes status $alias --json
        if ($LASTEXITCODE -ne 0) { throw 'Tunnel runtime status failed.' }
        $status = $statusJson | ConvertFrom-Json
        if ($status.healthy -and $status.ready) { break }
        Start-Sleep -Seconds 2
    }
    $status | Select-Object alias,healthy,ready,runtime_state,health_url | ConvertTo-Json
    if (-not ($status.healthy -and $status.ready)) { throw 'Tunnel did not become healthy and ready within the bounded wait.' }
    Write-Output 'Tunnel is ready. Verify a real tool invocation in ChatGPT; readiness alone is not WEB_CONNECTED_TESTED.'
} finally {
    $env:CONTROL_PLANE_API_KEY = $previousKey
    $secureKey = $null
}
