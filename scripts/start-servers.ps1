<#
.SYNOPSIS
  (Re)start the local Geo Grapher servers under the pinned environment (MCP 1.30.0).

.DESCRIPTION
  System Python may carry a different MCP major version, so servers always run
  under output/wheel-env. A running server is stopped only if its command line
  matches the expected service; the venv launcher parent is stopped with it.
  Logs: output/logs/serve-<port>.*.log   PIDs: output/logs/serve-<port>.pid

.EXAMPLE
  ./scripts/start-servers.ps1              # main workspace + graph hub
  ./scripts/start-servers.ps1 -Only hub    # just the graph hub
#>
param([ValidateSet('main','hub')][string[]]$Only = @('main','hub'))
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'output/wheel-env/Scripts/python.exe'
if (-not (Test-Path $python)) { throw "Pinned environment missing: $python" }
$env:PYTHONPATH = "$root/src;$root"
New-Item -ItemType Directory -Force (Join-Path $root 'output/logs') | Out-Null

$services = @{
  main = @{ port = 8765; match = 'serve --database .*toolset\.sqlite'; health = '/';
            args = @('-m','geographer','serve','--database',"$root/output/toolset.sqlite",'--catalog',"$root/output/named-graphs/catalog.sqlite",'--transport','http','--port','8765') }
  hub  = @{ port = 8774; match = 'serve-graphs .*named-graphs'; health = '/api/graphs';
            args = @('-m','geographer','serve-graphs','--catalog',"$root/output/named-graphs/catalog.sqlite",'--transport','http','--port','8774') }
}

foreach ($name in $Only) {
  $svc = $services[$name]; $port = $svc.port
  $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($listener) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($proc.CommandLine -notmatch $svc.match) { throw "Port $port is held by an unexpected process ($($proc.ProcessId)): $($proc.CommandLine)" }
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
    Stop-Process -Id $proc.ProcessId -Confirm:$false
    if ($parent -and $parent.CommandLine -match $svc.match) { Stop-Process -Id $parent.ProcessId -Confirm:$false -ErrorAction SilentlyContinue }
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 200 }
  }
  $log = Join-Path $root "output/logs/serve-$port"
  $started = Start-Process $python -ArgumentList $svc.args -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput "$log.out.log" -RedirectStandardError "$log.err.log" -PassThru
  Set-Content -LiteralPath "$log.pid" -Value $started.Id
  $deadline = (Get-Date).AddSeconds(60); $ok = $false
  while ((Get-Date) -lt $deadline -and -not $started.HasExited) {
    try { if ((Invoke-WebRequest "http://127.0.0.1:$port$($svc.health)" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { $ok = $true; break } } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $ok) { Get-Content "$log.err.log" -Tail 15; throw "$name did not become healthy on port $port" }
  "{0,-5} http://127.0.0.1:{1}/  pid {2}" -f $name, $port, $started.Id
}
