<#
.SYNOPSIS
  Release gate: full backend suite, frontend typecheck/build and browser suite.

.DESCRIPTION
  Always runs the *whole* pytest suite. A selected subset previously let a
  regression in an untouched module ship unnoticed. -Live additionally runs the
  read-only smoke against the running main workspace on :8765.

.EXAMPLE
  ./scripts/verify.ps1
  ./scripts/verify.ps1 -SkipBrowser -Live
#>
[CmdletBinding()]
param([switch]$SkipBrowser, [switch]$SkipFrontend, [switch]$Live,
  [switch]$QuietMachine, [string]$PresetCatalog = '',
  [string]$LatencyCatalog = '', [string]$GateOutput = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = "$root/src;$root"
$python = Join-Path $root 'output/wheel-env/Scripts/python.exe'
$results = [ordered]@{}
if (-not $GateOutput) { $GateOutput = Join-Path $root ('output/verify/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')) }
$GateOutput = [IO.Path]::GetFullPath($GateOutput)
if (Test-Path -LiteralPath $GateOutput) { throw 'Use a fresh GateOutput; first results must be preserved' }
New-Item -ItemType Directory -Path $GateOutput | Out-Null

function Step($name, [scriptblock]$body) {
  Write-Host "== $name" -ForegroundColor Cyan
  $start = Get-Date
  # Judge native tools by exit code: Windows PowerShell 5.1 turns any stderr line
  # (e.g. Vite's chunk-size advisory) into a terminating error under 'Stop'.
  $ErrorActionPreference = 'Continue'
  & $body 2>&1 | ForEach-Object { "$_" } | Out-Host
  $ErrorActionPreference = 'Stop'
  if ($LASTEXITCODE -ne 0) { $results[$name] = 'FAILED'; $results.GetEnumerator() | ForEach-Object { "{0,-22} {1}" -f $_.Key, $_.Value }; throw "$name failed (exit $LASTEXITCODE)" }
  $results[$name] = "ok ({0:N0}s)" -f ((Get-Date) - $start).TotalSeconds
}

Step 'backend (full suite)' { & $python -m pytest tests -q --ignore=tests/node_modules -p no:cacheprovider }
if (-not $SkipFrontend) {
  Step 'frontend typecheck' { npm run typecheck }
  Step 'frontend build' { npm run build }
  Step 'frontend unit' { npm run test:unit }
}
if (-not $SkipBrowser) { Step 'browser suite' { & ./node_modules/.bin/playwright.cmd test --config playwright.graphs.config.cjs } }
if ($Live) { Step 'live main workspace' { node scripts/qa-main-workspace.cjs } }
Step 'release wheel' { uv build --wheel --out-dir (Join-Path $GateOutput 'dist') }
$wheels = @(Get-ChildItem -LiteralPath (Join-Path $GateOutput 'dist') -Filter '*.whl')
if ($wheels.Count -ne 1) { throw 'Expected exactly one freshly built wheel' }
$wheel = $wheels[0].FullName
Step 'installed presets / caps' {
  $presetArgs = @('scripts/qa_mcp_presets.py', '--wheel', $wheel, '--out', (Join-Path $GateOutput 'presets-first.json'))
  if ($PresetCatalog) { $presetArgs += @('--catalog', $PresetCatalog) }
  & $python @presetArgs
}
if ($QuietMachine) {
  if (-not $LatencyCatalog) { $LatencyCatalog = Join-Path $root 'output/phase67-gates/wave2/catalog.sqlite' }
  Step 'C14 (3 cold processes)' {
    & $python scripts/qa_c14.py --quiet-machine --wheel $wheel --catalog $LatencyCatalog --out (Join-Path $GateOutput 'c14-first.json')
  }
} else { Write-Host 'C14 not run: use -QuietMachine on a quiet machine (prospective gate).' }

Write-Host ''
$results.GetEnumerator() | ForEach-Object { "{0,-22} {1}" -f $_.Key, $_.Value }
