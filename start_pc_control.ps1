param([switch]$NoPause, [switch]$SkipDiscord)
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
$private = Join-Path $base '.private'
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$statePath = Join-Path $private 'startup-state.json'
$localUrl = 'http://127.0.0.1:8002'
$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Local\PCControlServerLauncher', [ref]$created)
if (-not $created) { $mutex.Dispose(); exit 0 }
New-Item -ItemType Directory -Path $private -Force | Out-Null
$state = @{}
function Save-State {
    $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
}
function Test-Server([string]$url) {
    try {
        $spec = Invoke-RestMethod -Uri ($url.TrimEnd('/') + '/openapi.json') -TimeoutSec 5
        return $spec.info.title -eq 'PC Control Server'
    } catch { return $false }
}
function Get-OwnedProcess($record, [string]$expectedName) {
    if (-not $record) { return $null }
    $candidate = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.ProcessName -eq $expectedName -and
        [Math]::Abs(($candidate.StartTime.ToUniversalTime() - [datetime]::Parse($record.started).ToUniversalTime()).TotalSeconds) -lt 1) {
        return $candidate
    }
    return $null
}
function Record-Process($process) {
    return @{pid=$process.Id; started=$process.StartTime.ToUniversalTime().ToString('o')}
}
try {
    foreach ($required in @($python, $cloudflared, (Join-Path $base 'server_autostart.py'))) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Missing file: $required" }
    }
    if (Test-Path -LiteralPath $statePath) {
        $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        foreach ($property in $saved.PSObject.Properties) { $state[$property.Name] = $property.Value }
    }
    if (-not (Test-Server $localUrl)) {
        if (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue) {
            throw 'Port 8002 is occupied by another service.'
        }
        $serverArgs = '-u "' + (Join-Path $base 'server_autostart.py') + '"'
        $serverProcess = Start-Process -FilePath $python -ArgumentList $serverArgs -WorkingDirectory $base -WindowStyle Hidden -RedirectStandardOutput (Join-Path $private 'startup-server.out.log') -RedirectStandardError (Join-Path $private 'startup-server.err.log') -PassThru
        $state.server = Record-Process $serverProcess
        Save-State
        $ready = $false
        for ($i=0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if ($serverProcess.HasExited) { throw 'Server exited; see .private/startup-server.err.log.' }
            if (Test-Server $localUrl) { $ready = $true; break }
        }
        if (-not $ready) { throw 'Server did not become ready on port 8002.' }
    }
    Write-Output '[OK] Local PC-Control-Server: 8002'
    $tunnel = Get-OwnedProcess $state.tunnel 'cloudflared'
    $publicReady = $false
    if ($tunnel -and $state.url) { $publicReady = Test-Server $state.url }
    if (-not $publicReady) {
        if ($tunnel) { Stop-Process -Id $tunnel.Id -ErrorAction Stop }
        $state.Remove('url')
        $tunnelLog = Join-Path $private 'cloudflare.err.log'
        $tunnel = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url',$localUrl,'--no-autoupdate','--metrics','127.0.0.1:0') -WorkingDirectory $base -WindowStyle Hidden -RedirectStandardOutput (Join-Path $private 'cloudflare.out.log') -RedirectStandardError $tunnelLog -PassThru
        $state.tunnel = Record-Process $tunnel
        Save-State
        for ($i=0; $i -lt 75; $i++) {
            Start-Sleep -Seconds 1
            if ($tunnel.HasExited) { throw 'Cloudflare exited; see .private/cloudflare.err.log.' }
            $logs = Get-Content -LiteralPath $tunnelLog -Raw -ErrorAction SilentlyContinue
            $urlMatch = [regex]::Match([string]$logs, 'https://[a-z0-9-]+\.trycloudflare\.com')
            if ($urlMatch.Success) { $state.url = $urlMatch.Value; Save-State; break }
        }
        if (-not $state.url) { throw 'Cloudflare public URL was not created.' }
        for ($i=0; $i -lt 30; $i++) {
            if (Test-Server $state.url) { $publicReady = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $publicReady) { throw 'Cloudflare public URL is not responding yet.' }
    } else { Write-Output '[OK] Existing Cloudflare tunnel reused.' }
    Write-Output ('[OK] Public URL: ' + $state.url)
    @('Local: ' + $localUrl, 'Public: ' + $state.url, 'GPT: ' + $state.url + '/gpt') | Set-Content -LiteralPath (Join-Path $private 'addresses.txt') -Encoding UTF8
    $webhookFile = Join-Path $private 'discord-webhook.txt'
    if (-not $SkipDiscord -and $state.notifiedUrl -ne $state.url -and (Test-Path -LiteralPath $webhookFile)) {
        $webhook = (Get-Content -LiteralPath $webhookFile -Raw).Trim()
        $body = @{content = "PC-Control-Server`n$($state.url)`nGPT: $($state.url)/gpt"} | ConvertTo-Json
        Invoke-RestMethod -Uri $webhook -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) | Out-Null
        $state.notifiedUrl = $state.url
        Save-State
        Write-Output '[OK] Discord link sent.'
    }
    exit 0
} catch {
    $message = $_.Exception.Message
    if ($message -match 'discord|webhook') { $message = 'Notification failed; private configuration omitted.' }
    Write-Output ('[ERROR] ' + $message)
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}