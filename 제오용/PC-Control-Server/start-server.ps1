$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$listener = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host 'Port 8002 is already listening.'
    exit 0
}
$pythonPath = (Get-Command python).Source
Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','server:app','--host','127.0.0.1','--port','8002' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'data/server.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'data/server.stderr.log')
