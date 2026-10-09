param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$baseDir = Split-Path -Parent $PSScriptRoot
$guestName = -join ([char[]](0xC190, 0xB2D8, 0xC6A9))
$controlName = -join ([char[]](0xC81C, 0xC624, 0xC6A9))
$guestDir = Join-Path $baseDir $guestName
$controlDir = Join-Path $baseDir $controlName
$serverDir = Join-Path $controlDir 'PC-Control-Server'
$measureExe = Join-Path $guestDir 'PC-Measure.exe'
$tunnelExe = Join-Path $controlDir 'tunnel-client.exe'
$serverFile = Join-Path $serverDir 'server.py'
$keyFile = Join-Path $PSScriptRoot 'api-key.txt'

try {
    if (-not (Test-Path -LiteralPath $keyFile)) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'api-key.example.txt') -Destination $keyFile
    }
    foreach ($path in @($measureExe, $tunnelExe, $serverFile, $keyFile)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required file missing: $path"
        }
    }
    $python = (Get-Command python -ErrorAction Stop).Source
    if ($CheckOnly) {
        & $python -B (Join-Path $PSScriptRoot 'supervisor.py') --check
        if ($LASTEXITCODE -ne 0) { throw 'Supervisor validation failed.' }
        Write-Host 'OK: launch paths and Python are available. No applications started.'
        exit 0
    }

    $apiKey = (Get-Content -LiteralPath $keyFile -Raw -Encoding UTF8).Trim()
    if (-not $apiKey -or $apiKey -eq 'PASTE_API_KEY_HERE') {
        Start-Process notepad.exe -ArgumentList ('"{0}"' -f $keyFile) -Wait
        $apiKey = (Get-Content -LiteralPath $keyFile -Raw -Encoding UTF8).Trim()
    }
    if (-not $apiKey -or $apiKey -eq 'PASTE_API_KEY_HERE' -or $apiKey -match '[\r\n]') {
        throw 'Enter only your API key on one line in api-key.txt, save, and run again.'
    }
    $env:CONTROL_PLANE_API_KEY = $apiKey

    $listener = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw 'Port 8002 is already in use. Close the existing server before starting this group.'
    }

    $measureRunning = Get-Process -Name 'PC-Measure' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $measureExe }
    if ($measureRunning) {
        throw 'PC-Measure is already running. Close it before starting this group.'
    }

    & $python -B (Join-Path $PSScriptRoot 'supervisor.py')
    exit $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
