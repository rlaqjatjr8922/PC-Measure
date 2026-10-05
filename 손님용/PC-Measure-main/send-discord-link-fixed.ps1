$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# Run this script from the project folder. It will:
# 1) start server.py
# 2) create a fresh Cloudflare Quick Tunnel
# 3) verify /system/status through the public URL
# 4) send "0001 <new URL>" to Discord
# 5) keep the server/tunnel alive and print logs if either process fails

$projectDir = $PSScriptRoot
$serverPy   = Join-Path $projectDir 'server.py'
$configPy   = Join-Path $projectDir 'config.py'
$logDir     = Join-Path $projectDir '.logs\send-discord-link'

$webhookUrl = 'YOUR_DISCORD_WEBHOOK_URL'

function Write-Step([string]$Text) {
    Write-Host "[+] $Text" -ForegroundColor Cyan
}

function Show-Log([string]$Title, [string]$Path) {
    Write-Host "`n===== $Title =====" -ForegroundColor Yellow
    if (Test-Path -LiteralPath $Path) {
        Get-Content -LiteralPath $Path -Tail 120 -ErrorAction SilentlyContinue
    }
    else {
        Write-Host '(log file not created)'
    }
}

function Get-ServerPort {
    param([string]$ConfigPath, [int]$DefaultPort = 8010)

    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        Write-Warning "config.py not found. Using default port $DefaultPort."
        return $DefaultPort
    }

    $lines = Get-Content -LiteralPath $ConfigPath -ErrorAction Stop

    # Prefer the HTTP/API server port and avoid accidentally picking an unrelated port.
    $preferredNames = @('SERVER_PORT', 'API_PORT', 'HTTP_PORT', 'PORT')
    foreach ($name in $preferredNames) {
        foreach ($line in $lines) {
            if ($line -match ("(?i)\b" + [regex]::Escape($name) + "\b") -and $line -match '\b(\d{2,5})\b') {
                $candidate = [int]$Matches[1]
                if ($candidate -ge 1 -and $candidate -le 65535) {
                    return $candidate
                }
            }
        }
    }

    # Also supports patterns such as uvicorn.run(..., port=8010)
    $raw = $lines -join "`n"
    if ($raw -match '(?i)\bport\s*=\s*(\d{2,5})') {
        $candidate = [int]$Matches[1]
        if ($candidate -ge 1 -and $candidate -le 65535) {
            return $candidate
        }
    }

    Write-Warning "Could not detect a port in config.py. Using default port $DefaultPort."
    return $DefaultPort
}

function Find-Cloudflared {
    if ($env:CLOUDFLARED_PATH -and (Test-Path -LiteralPath $env:CLOUDFLARED_PATH)) {
        return (Resolve-Path -LiteralPath $env:CLOUDFLARED_PATH).Path
    }

    $cmd = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue }
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        (Join-Path $projectDir 'cloudflared.exe'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\cloudflared.exe'),
        (Join-Path $env:USERPROFILE 'scoop\shims\cloudflared.exe'),
        (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe'),
        (Join-Path $env:ProgramFiles 'Cloudflare\cloudflared.exe')
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    # winget often stores the real executable inside a versioned Packages folder.
    $wingetPackages = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    if (Test-Path -LiteralPath $wingetPackages) {
        $found = Get-ChildItem -LiteralPath $wingetPackages -Filter 'cloudflared.exe' -File -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }

    # Last small-scope fallback: look inside this project only.
    $foundLocal = Get-ChildItem -LiteralPath $projectDir -Filter 'cloudflared.exe' -File -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($foundLocal) { return $foundLocal.FullName }

    throw @"
cloudflared.exe was not found.
Checked PATH, project folder, WinGet Links/Packages, Scoop, and common Program Files locations.
If cloudflared.exe is elsewhere, set it first, for example:
  `$env:CLOUDFLARED_PATH = 'C:\path\to\cloudflared.exe'
  .\send-discord-link-fixed.ps1
"@
}

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [int]$TimeoutSec = 10
    )
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $serverPy)) {
    throw "server.py not found: $serverPy"
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$serverOut = Join-Path $logDir 'server.stdout.log'
$serverErr = Join-Path $logDir 'server.stderr.log'
$tunnelOut = Join-Path $logDir 'cloudflared.stdout.log'
$tunnelErr = Join-Path $logDir 'cloudflared.stderr.log'

# Start clean logs on each run so an old trycloudflare URL cannot be reused accidentally.
@($serverOut, $serverErr, $tunnelOut, $tunnelErr) | ForEach-Object {
    Set-Content -LiteralPath $_ -Value '' -Encoding UTF8
}

$port = Get-ServerPort -ConfigPath $configPy -DefaultPort 8010
$localBase = "http://127.0.0.1:$port"
$statusPath = '/system/status'
$localStatus = "$localBase$statusPath"

$serverProcess = $null
$tunnelProcess = $null
$startedServer = $false

try {
    Write-Step "Project: $projectDir"
    Write-Step "Server port from config/default: $port"

    if (Test-HttpEndpoint -Uri $localStatus -TimeoutSec 2) {
        Write-Step "Server is already responding at $localStatus; reusing it."
    }
    else {
        $pythonCmd = Get-Command py.exe -ErrorAction SilentlyContinue
        $pythonArgs = @()
        if ($pythonCmd) {
            $pythonExe = $pythonCmd.Source
            $pythonArgs = @('-3', 'server.py')
        }
        else {
            $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $pythonCmd) { $pythonCmd = Get-Command python -ErrorAction SilentlyContinue }
            if (-not $pythonCmd) { throw 'Python (py.exe/python.exe) was not found in PATH.' }
            $pythonExe = $pythonCmd.Source
            $pythonArgs = @('server.py')
        }

        Write-Step "Starting server.py with $pythonExe"
        $serverProcess = Start-Process -FilePath $pythonExe -ArgumentList $pythonArgs -WorkingDirectory $projectDir `
            -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr -PassThru -WindowStyle Hidden
        $startedServer = $true

        $serverReady = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if ($serverProcess.HasExited) { break }
            if (Test-HttpEndpoint -Uri $localStatus -TimeoutSec 2) {
                $serverReady = $true
                break
            }
        }

        if (-not $serverReady) {
            throw "server.py did not become ready at $localStatus."
        }
        Write-Step "Local status OK: $localStatus"
    }

    $cloudflared = Find-Cloudflared
    Write-Step "cloudflared: $cloudflared"
    Write-Step 'Creating a new Cloudflare Quick Tunnel...'

    $tunnelProcess = Start-Process -FilePath $cloudflared `
        -ArgumentList @('tunnel', '--url', $localBase, '--no-autoupdate') `
        -WorkingDirectory $projectDir `
        -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr `
        -PassThru -WindowStyle Hidden

    $publicUrl = $null
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 1
        if ($tunnelProcess.HasExited) { break }

        $combined = ''
        if (Test-Path -LiteralPath $tunnelOut) { $combined += (Get-Content -LiteralPath $tunnelOut -Raw -ErrorAction SilentlyContinue) }
        if (Test-Path -LiteralPath $tunnelErr) { $combined += "`n" + (Get-Content -LiteralPath $tunnelErr -Raw -ErrorAction SilentlyContinue) }

        $matches = [regex]::Matches($combined, 'https://[a-z0-9-]+\.trycloudflare\.com', 'IgnoreCase')
        if ($matches.Count -gt 0) {
            $publicUrl = $matches[$matches.Count - 1].Value.TrimEnd('/')
            break
        }
    }

    if (-not $publicUrl) {
        throw 'Could not obtain a fresh https://...trycloudflare.com URL from cloudflared logs.'
    }

    Write-Step "New public URL: $publicUrl"

    $publicStatus = "$publicUrl$statusPath"
    Write-Step "Verifying public endpoint: $publicStatus"

    $publicReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($tunnelProcess.HasExited) { break }
        if (Test-HttpEndpoint -Uri $publicStatus -TimeoutSec 10) {
            $publicReady = $true
            break
        }
        Start-Sleep -Seconds 2
    }

    if (-not $publicReady) {
        throw "Public /system/status did not return HTTP 2xx: $publicStatus"
    }
    Write-Step 'Public /system/status OK.'

    $message = "0001 $publicUrl"
    $payload = @{
        content = $message
        allowed_mentions = @{ parse = @() }
    } | ConvertTo-Json -Depth 4 -Compress

    Write-Step 'Sending new URL to Discord webhook...'
    $null = Invoke-RestMethod -Uri ($webhookUrl + '?wait=true') -Method Post `
        -ContentType 'application/json; charset=utf-8' `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) -TimeoutSec 30
    Write-Step "Discord sent: $message"

    Write-Host "`nServer and tunnel are running. Keep this PowerShell window open." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop them." -ForegroundColor Green
    Write-Host "Logs: $logDir`n"

    while ($true) {
        Start-Sleep -Seconds 5

        if ($startedServer -and $serverProcess -and $serverProcess.HasExited) {
            throw "server.py exited unexpectedly with code $($serverProcess.ExitCode)."
        }
        if ($tunnelProcess -and $tunnelProcess.HasExited) {
            throw "cloudflared exited unexpectedly with code $($tunnelProcess.ExitCode)."
        }
    }
}
catch {
    Write-Host "`n[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Show-Log 'server stdout' $serverOut
    Show-Log 'server stderr' $serverErr
    Show-Log 'cloudflared stdout' $tunnelOut
    Show-Log 'cloudflared stderr' $tunnelErr
    exit 1
}
finally {
    # Ctrl+C / script termination: only stop processes that this script started.
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($startedServer -and $serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

