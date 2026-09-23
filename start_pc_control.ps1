# ============================================================
# PC-Control-Server Launcher
# Windows PowerShell 5.1
# ============================================================

$ErrorActionPreference = "Stop"

# ============================================================
# 기본 경로 / 설정
# ============================================================

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BaseDir

$Server = Join-Path $BaseDir "server.py"

$LocalHost = "127.0.0.1"
$ServerPort = 8002

# Pinggy Web Debugger용 로컬 포트
$PinggyApiPort = 4300

# ============================================================
# Discord Webhook
# 기존 Discord 링크 전송 기능 유지
# ============================================================

$DiscordWebhook = "https://discord.com/api/webhooks/1551901664942886983/jweaYpklgGGahbHW_aay-ZDffCs4zR3SlVzd4WzMxJqUHk_LvlZjucbDf60LS60jXI9w"

# ============================================================
# Pinggy 로그
# ============================================================

$PinggyStdout = Join-Path $BaseDir "pinggy_stdout.log"
$PinggyStderr = Join-Path $BaseDir "pinggy_stderr.log"

Clear-Host

Write-Host "========================================"
Write-Host " PC-Control-Server Launcher"
Write-Host "========================================"
Write-Host ""

# ============================================================
# ANSI Escape Sequence 제거
# ============================================================

function Remove-Ansi {

    param(
        [string]$Text
    )

    if ([string]::IsNullOrEmpty($Text)) {
        return ""
    }

    # CSI
    $Text = $Text -replace "`e\[[0-?]*[ -/]*[@-~]", ""

    # OSC
    $Text = $Text -replace "`e\][^\x07]*(?:\x07|`e\\)", ""

    # 기타 제어문자
    $Text = $Text -replace "[\x00-\x08\x0B\x0C\x0E-\x1F]", ""

    return $Text
}

# ============================================================
# Pinggy 로그 읽기
# ============================================================

function Get-PinggyLog {

    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    try {

        $Text = [System.IO.File]::ReadAllText($Path)

        return (Remove-Ansi $Text)

    }
    catch {

        return ""
    }
}

# ============================================================
# Pinggy stdout / stderr 전체 출력
# ============================================================

function Show-PinggyLogs {

    Write-Host ""
    Write-Host "========================================"
    Write-Host " Pinggy STDOUT"
    Write-Host "========================================"

    $Stdout = Get-PinggyLog $PinggyStdout

    if ([string]::IsNullOrWhiteSpace($Stdout)) {

        Write-Host "(empty)"

    }
    else {

        Write-Host $Stdout
    }

    Write-Host ""
    Write-Host "========================================"
    Write-Host " Pinggy STDERR"
    Write-Host "========================================"

    $Stderr = Get-PinggyLog $PinggyStderr

    if ([string]::IsNullOrWhiteSpace($Stderr)) {

        Write-Host "(empty)"

    }
    else {

        Write-Host $Stderr
    }

    Write-Host ""
}

# ============================================================
# stdout + stderr에서 HTTPS URL 찾기
#
# Pinggy 도메인명은 하드코딩하지 않음
# ============================================================

function Find-HttpsUrlFromLogs {

    $Stdout = Get-PinggyLog $PinggyStdout
    $Stderr = Get-PinggyLog $PinggyStderr

    $Combined = $Stdout + "`r`n" + $Stderr

    if ([string]::IsNullOrWhiteSpace($Combined)) {
        return $null
    }

    $Matches = [regex]::Matches(
        $Combined,
        'https://[^\s<>"''\]\[\(\)]+',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    foreach ($Match in $Matches) {

        $Candidate = $Match.Value.Trim()

        $Candidate = $Candidate.TrimEnd(
            '.', ',', ';', ':', ')', ']', '}', '"', "'"
        )

        try {

            $Uri = New-Object System.Uri($Candidate)

            if (
                $Uri.Scheme -eq "https" -and
                -not [string]::IsNullOrWhiteSpace($Uri.Host) -and
                $Uri.Host -ne "localhost" -and
                $Uri.Host -ne "127.0.0.1"
            ) {

                return $Uri.AbsoluteUri.TrimEnd("/")
            }

        }
        catch {
        }
    }

    return $null
}

# ============================================================
# Pinggy Web Debugger API에서 URL 가져오기
#
# 공식 Pinggy API:
# http://127.0.0.1:<포트>/urls
# ============================================================

function Get-PinggyUrlFromApi {

    $ApiUrl = "http://127.0.0.1:$PinggyApiPort/urls"

    try {

        $Response = Invoke-RestMethod `
            -Uri $ApiUrl `
            -Method Get `
            -TimeoutSec 2

        if ($null -eq $Response) {
            return $null
        }

        if ($null -eq $Response.urls) {
            return $null
        }

        foreach ($Url in $Response.urls) {

            if ([string]::IsNullOrWhiteSpace($Url)) {
                continue
            }

            try {

                $Uri = New-Object System.Uri($Url)

                if (
                    $Uri.Scheme -eq "https" -and
                    -not [string]::IsNullOrWhiteSpace($Uri.Host)
                ) {

                    return $Uri.AbsoluteUri.TrimEnd("/")
                }

            }
            catch {
            }
        }

    }
    catch {
    }

    return $null
}

# ============================================================
# Discord Webhook 전송
# ============================================================

function Send-DiscordLink {

    param(
        [string]$Url
    )

    if ([string]::IsNullOrWhiteSpace($DiscordWebhook)) {

        Write-Host ""
        Write-Host "[WARNING] Discord Webhook URL not configured."
        Write-Host "[URL] $Url"

        return $false
    }

    try {

        $Payload = @{
            content = $Url
        }

        $Json = $Payload | ConvertTo-Json -Compress
        $Utf8 = [System.Text.Encoding]::UTF8.GetBytes($Json)

        Invoke-RestMethod `
            -Uri $DiscordWebhook `
            -Method Post `
            -ContentType "application/json; charset=utf-8" `
            -Body $Utf8 `
            | Out-Null

        Write-Host "[OK] Discord webhook sent."

        return $true
    }
    catch {

        Write-Host ""
        Write-Host "[ERROR] Discord webhook failed."
        Write-Host $_.Exception.Message
        Write-Host ""
        Write-Host "[GPT URL]"
        Write-Host $Url

        return $false
    }
}

# ============================================================
# 로컬 포트가 비어있는지 확인
# ============================================================

function Test-LocalPortFree {

    param(
        [int]$Port
    )

    try {

        $Listener = New-Object System.Net.Sockets.TcpListener(
            [System.Net.IPAddress]::Loopback,
            $Port
        )

        $Listener.Start()
        $Listener.Stop()

        return $true

    }
    catch {

        return $false
    }
}

# ============================================================
# Python 찾기
# ============================================================

Write-Host "[CHECK] Finding Python..."

$PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue

if ($null -eq $PythonCommand) {

    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
}

if ($null -eq $PythonCommand) {

    Write-Host ""
    Write-Host "[ERROR] Python not found."

    Read-Host "Press Enter"
    exit 1
}

$Python = $PythonCommand.Source

Write-Host "[OK] Python:"
Write-Host $Python
Write-Host ""

# ============================================================
# server.py 확인
# ============================================================

if (-not (Test-Path $Server)) {

    Write-Host "[ERROR] server.py not found:"
    Write-Host $Server

    Read-Host "Press Enter"
    exit 1
}

Write-Host "[OK] server.py found."
Write-Host ""

# ============================================================
# SSH 찾기
# ============================================================

Write-Host "[CHECK] Finding SSH..."

$SshCommand = Get-Command ssh.exe -ErrorAction SilentlyContinue

if ($null -eq $SshCommand) {

    Write-Host ""
    Write-Host "[ERROR] Windows OpenSSH ssh.exe not found."

    Read-Host "Press Enter"
    exit 1
}

$Ssh = $SshCommand.Source

Write-Host "[OK] SSH:"
Write-Host $Ssh
Write-Host ""

# ============================================================
# ssh-keygen 찾기
# ============================================================

$SshKeygenCommand = Get-Command ssh-keygen.exe -ErrorAction SilentlyContinue

if ($null -eq $SshKeygenCommand) {

    Write-Host ""
    Write-Host "[ERROR] ssh-keygen.exe not found."

    Read-Host "Press Enter"
    exit 1
}

# ============================================================
# SSH 키 확인 / 자동 생성
#
# PowerShell 5.1에서
#
#   ssh-keygen -N ""
#
# 빈 문자열 전달 문제가 있기 때문에
# ProcessStartInfo.Arguments에 명령줄을 직접 작성
# ============================================================

$SshDir = Join-Path $env:USERPROFILE ".ssh"

$PrivateKey = Join-Path $SshDir "id_ed25519"
$PublicKey  = Join-Path $SshDir "id_ed25519.pub"

if (-not (Test-Path $PrivateKey)) {

    Write-Host "[CHECK] SSH key not found."
    Write-Host "[INFO] Creating SSH key..."
    Write-Host ""

    if (-not (Test-Path $SshDir)) {

        New-Item `
            -ItemType Directory `
            -Path $SshDir `
            -Force `
            | Out-Null
    }

    try {

        $KeyInfo = New-Object System.Diagnostics.ProcessStartInfo

        $KeyInfo.FileName = $SshKeygenCommand.Source

        # 중요:
        # -N "" 를 문자열에 직접 넣어서
        # PowerShell 5.1의 빈 인수 처리 문제 우회

        $KeyInfo.Arguments = (
            '-q -t ed25519 -N "" -f "' +
            $PrivateKey +
            '"'
        )

        $KeyInfo.UseShellExecute = $false
        $KeyInfo.CreateNoWindow = $true

        $KeyProcess = New-Object System.Diagnostics.Process
        $KeyProcess.StartInfo = $KeyInfo

        [void]$KeyProcess.Start()

        $KeyProcess.WaitForExit()

        $KeygenExitCode = $KeyProcess.ExitCode
    }
    catch {

        Write-Host ""
        Write-Host "[ERROR] Failed to run ssh-keygen."
        Write-Host $_.Exception.Message

        Read-Host "Press Enter"
        exit 1
    }

    if ($KeygenExitCode -ne 0) {

        Write-Host ""
        Write-Host "[ERROR] SSH key generation failed."
        Write-Host "[EXIT CODE] $KeygenExitCode"

        Read-Host "Press Enter"
        exit 1
    }

    if (-not (Test-Path $PrivateKey)) {

        Write-Host ""
        Write-Host "[ERROR] SSH private key was not created."

        Read-Host "Press Enter"
        exit 1
    }

    Write-Host "[OK] SSH key created:"
    Write-Host $PrivateKey
    Write-Host ""

}
else {

    Write-Host "[OK] SSH key found:"
    Write-Host $PrivateKey
    Write-Host ""
}

# ============================================================
# 이전 Pinggy 로그 삭제
# ============================================================

Remove-Item $PinggyStdout -Force -ErrorAction SilentlyContinue
Remove-Item $PinggyStderr -Force -ErrorAction SilentlyContinue

# ============================================================
# [1/4] server.py 실행
# 기존 Mission 선택 방식 유지
# ============================================================

Write-Host "========================================"
Write-Host "[1/4] Starting server.py"
Write-Host "========================================"
Write-Host ""

$ServerCommand = "& '$Python' '$Server'"

$ServerProcess = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $ServerCommand
    ) `
    -WorkingDirectory $BaseDir `
    -PassThru

# ============================================================
# [2/4] Mission 선택 + 8002 포트 대기
# ============================================================

Write-Host "[2/4] Waiting for Mission selection..."
Write-Host ""
Write-Host "Select Mission in the server.py window."
Write-Host ""

$ServerReady = $false

while (-not $ServerReady) {

    if ($ServerProcess.HasExited) {

        Write-Host ""
        Write-Host "[ERROR] server.py process exited."

        Read-Host "Press Enter"
        exit 1
    }

    try {

        $Client = New-Object System.Net.Sockets.TcpClient

        $Async = $Client.BeginConnect(
            $LocalHost,
            $ServerPort,
            $null,
            $null
        )

        $Connected = $Async.AsyncWaitHandle.WaitOne(500)

        if ($Connected -and $Client.Connected) {

            try {
                $Client.EndConnect($Async)
            }
            catch {
            }

            $ServerReady = $true
        }

        $Client.Close()

    }
    catch {
    }

    if (-not $ServerReady) {
        Start-Sleep -Milliseconds 500
    }
}

Write-Host ""
Write-Host "[OK] Server running:"
Write-Host "http://${LocalHost}:${ServerPort}"
Write-Host ""

# ============================================================
# Pinggy Web Debugger 로컬 포트 확보
# ============================================================

if (-not (Test-LocalPortFree $PinggyApiPort)) {

    Write-Host "[WARNING] Port $PinggyApiPort already in use."
    Write-Host "[CHECK] Finding free Pinggy API port..."
    Write-Host ""

    $FoundPort = $null

    for ($P = 4301; $P -le 4399; $P++) {

        if (Test-LocalPortFree $P) {

            $FoundPort = $P
            break
        }
    }

    if ($null -eq $FoundPort) {

        Write-Host "[ERROR] No free Pinggy API port found."

        Read-Host "Press Enter"
        exit 1
    }

    $PinggyApiPort = $FoundPort

    Write-Host "[OK] Pinggy API port:"
    Write-Host $PinggyApiPort
    Write-Host ""
}

# ============================================================
# [3/4] Pinggy Tunnel 실행
#
# Windows에서는 localhost 대신 127.0.0.1 사용
# ============================================================

Write-Host "========================================"
Write-Host "[3/4] Starting Pinggy Tunnel"
Write-Host "========================================"
Write-Host ""

# ============================================================
# SSH 명령줄 직접 생성
#
# Start-Process ArgumentList의 따옴표/공백 문제를 피하기 위해
# ProcessStartInfo 사용
# ============================================================

$SshArgumentString = (
    '-o StrictHostKeyChecking=no ' +
    '-o ServerAliveInterval=30 ' +
    '-o ServerAliveCountMax=3 ' +
    '-o ExitOnForwardFailure=yes ' +
    '-o BatchMode=yes ' +
    '-i "' + $PrivateKey + '" ' +
    '-p 443 ' +
    '-R0:127.0.0.1:' + $ServerPort + ' ' +
    '-L' + $PinggyApiPort + ':127.0.0.1:4300 ' +
    'free.pinggy.io'
)

try {

    $PinggyInfo = New-Object System.Diagnostics.ProcessStartInfo

    $PinggyInfo.FileName = $Ssh

    $PinggyInfo.Arguments = $SshArgumentString

    $PinggyInfo.WorkingDirectory = $BaseDir

    $PinggyInfo.UseShellExecute = $false

    $PinggyInfo.CreateNoWindow = $true

    $PinggyInfo.RedirectStandardOutput = $true
    $PinggyInfo.RedirectStandardError = $true

    $PinggyProcess = New-Object System.Diagnostics.Process

    $PinggyProcess.StartInfo = $PinggyInfo

    [void]$PinggyProcess.Start()

}
catch {

    Write-Host ""
    Write-Host "[ERROR] Failed to start Pinggy SSH."
    Write-Host $_.Exception.Message

    Read-Host "Press Enter"
    exit 1
}

# ============================================================
# stdout/stderr 비동기 저장
#
# RedirectStandardOutput을 켠 상태에서 읽지 않으면
# 버퍼가 가득 차서 프로세스가 멈출 수 있으므로
# BackgroundReader 방식으로 계속 파일에 기록
# ============================================================

$StdoutWriter = New-Object System.IO.StreamWriter(
    $PinggyStdout,
    $false,
    [System.Text.Encoding]::UTF8
)

$StderrWriter = New-Object System.IO.StreamWriter(
    $PinggyStderr,
    $false,
    [System.Text.Encoding]::UTF8
)

$StdoutWriter.AutoFlush = $true
$StderrWriter.AutoFlush = $true

$StdoutEvent = Register-ObjectEvent `
    -InputObject $PinggyProcess `
    -EventName OutputDataReceived `
    -Action {

        if ($null -ne $EventArgs.Data) {

            $Event.MessageData.WriteLine($EventArgs.Data)
        }

    } `
    -MessageData $StdoutWriter

$StderrEvent = Register-ObjectEvent `
    -InputObject $PinggyProcess `
    -EventName ErrorDataReceived `
    -Action {

        if ($null -ne $EventArgs.Data) {

            $Event.MessageData.WriteLine($EventArgs.Data)
        }

    } `
    -MessageData $StderrWriter

$PinggyProcess.BeginOutputReadLine()
$PinggyProcess.BeginErrorReadLine()

Write-Host "Waiting for Pinggy public URL..."
Write-Host ""

# ============================================================
# Pinggy URL 대기
#
# 1순위: 공식 /urls API
# 2순위: stdout/stderr에서 URL 파싱
# ============================================================

$PublicUrl = $null

$StartTime = Get-Date
$LastDebugPrint = -1

while ($null -eq $PublicUrl) {

    # ========================================================
    # Pinggy SSH가 종료된 경우
    # ========================================================

    if ($PinggyProcess.HasExited) {

        Start-Sleep -Milliseconds 300

        Write-Host ""
        Write-Host "[ERROR] Pinggy SSH process exited."
        Write-Host "[EXIT CODE] $($PinggyProcess.ExitCode)"

        Show-PinggyLogs

        try {
            Unregister-Event -SourceIdentifier $StdoutEvent.Name -ErrorAction SilentlyContinue
        }
        catch {
        }

        try {
            Unregister-Event -SourceIdentifier $StderrEvent.Name -ErrorAction SilentlyContinue
        }
        catch {
        }

        try {
            $StdoutWriter.Close()
            $StderrWriter.Close()
        }
        catch {
        }

        Read-Host "Press Enter"

        exit 1
    }

    # ========================================================
    # 1순위
    # Pinggy 공식 Web Debugger /urls
    # ========================================================

    $PublicUrl = Get-PinggyUrlFromApi

    # ========================================================
    # 2순위
    # stdout + stderr fallback
    # ========================================================

    if ($null -eq $PublicUrl) {

        $PublicUrl = Find-HttpsUrlFromLogs
    }

    if ($null -ne $PublicUrl) {

        break
    }

    $Elapsed = [int](((Get-Date) - $StartTime).TotalSeconds)

    # ========================================================
    # 5초마다 현재 상태 출력
    # ========================================================

    if (
        $Elapsed -ge 5 -and
        ($Elapsed % 5) -eq 0 -and
        $LastDebugPrint -ne $Elapsed
    ) {

        $LastDebugPrint = $Elapsed

        Write-Host "[WAIT] Pinggy URL not ready... ${Elapsed}s"

        $TempStdout = Get-PinggyLog $PinggyStdout
        $TempStderr = Get-PinggyLog $PinggyStderr

        if (-not [string]::IsNullOrWhiteSpace($TempStdout)) {

            Write-Host ""
            Write-Host "[SSH STDOUT]"
            Write-Host $TempStdout
        }

        if (-not [string]::IsNullOrWhiteSpace($TempStderr)) {

            Write-Host ""
            Write-Host "[SSH STDERR]"
            Write-Host $TempStderr
        }

        Write-Host ""
    }

    # ========================================================
    # 60초 Timeout
    # ========================================================

    if ($Elapsed -ge 60) {

        Write-Host ""
        Write-Host "[ERROR] Pinggy URL timeout."
        Write-Host ""
        Write-Host "HTTPS public URL was not detected."

        Show-PinggyLogs

        if (-not $PinggyProcess.HasExited) {

            try {
                $PinggyProcess.Kill()
            }
            catch {
            }
        }

        try {
            Unregister-Event -SourceIdentifier $StdoutEvent.Name -ErrorAction SilentlyContinue
        }
        catch {
        }

        try {
            Unregister-Event -SourceIdentifier $StderrEvent.Name -ErrorAction SilentlyContinue
        }
        catch {
        }

        try {

            $StdoutWriter.Close()
            $StderrWriter.Close()

        }
        catch {
        }

        Read-Host "Press Enter"

        exit 1
    }

    Start-Sleep -Milliseconds 500
}

# ============================================================
# 공개 URL / GPT URL 생성
# ============================================================

$PublicUrl = $PublicUrl.TrimEnd("/")

$GptUrl = $PublicUrl.TrimEnd("/") + "/gpt"

Write-Host ""
Write-Host "[OK] Pinggy public URL:"
Write-Host $PublicUrl
Write-Host ""

Write-Host "[OK] GPT URL:"
Write-Host $GptUrl
Write-Host ""

# ============================================================
# [4/4] Discord Webhook
# ============================================================

Write-Host "========================================"
Write-Host "[4/4] Sending Discord Link"
Write-Host "========================================"
Write-Host ""

$DiscordSent = Send-DiscordLink $GptUrl

if (-not $DiscordSent) {

    Write-Host ""
    Write-Host "[WARNING] Discord send failed."
}

# ============================================================
# 실행 완료
# ============================================================

Write-Host ""
Write-Host "========================================"
Write-Host " PC-Control-Server RUNNING"
Write-Host "========================================"
Write-Host ""

Write-Host "Local:"
Write-Host "http://${LocalHost}:${ServerPort}"
Write-Host ""

Write-Host "Public:"
Write-Host $PublicUrl
Write-Host ""

Write-Host "GPT:"
Write-Host $GptUrl
Write-Host ""

Write-Host "PowerShell window must stay open."
Write-Host ""

# ============================================================
# 서버 / Pinggy 유지
# ============================================================

try {

    while ($true) {

        Start-Sleep -Seconds 1

        # ====================================================
        # Pinggy SSH 종료 감지
        # ====================================================

        if ($PinggyProcess.HasExited) {

            Start-Sleep -Milliseconds 300

            Write-Host ""
            Write-Host "========================================"
            Write-Host " Pinggy Tunnel Stopped"
            Write-Host "========================================"

            Write-Host ""
            Write-Host "[EXIT CODE] $($PinggyProcess.ExitCode)"

            Show-PinggyLogs

            break
        }

        # ====================================================
        # server.py 종료 감지
        # ====================================================

        if ($ServerProcess.HasExited) {

            Write-Host ""
            Write-Host "[WARNING] server.py process exited."
            Write-Host ""

            if (-not $PinggyProcess.HasExited) {

                try {
                    $PinggyProcess.Kill()
                }
                catch {
                }
            }

            break
        }
    }
}
finally {

    # ========================================================
    # Pinggy 정리
    # ========================================================

    if (
        $null -ne $PinggyProcess -and
        -not $PinggyProcess.HasExited
    ) {

        try {
            $PinggyProcess.Kill()
        }
        catch {
        }
    }

    # ========================================================
    # 이벤트 해제
    # ========================================================

    try {

        if ($null -ne $StdoutEvent) {

            Unregister-Event `
                -SourceIdentifier $StdoutEvent.Name `
                -ErrorAction SilentlyContinue
        }

    }
    catch {
    }

    try {

        if ($null -ne $StderrEvent) {

            Unregister-Event `
                -SourceIdentifier $StderrEvent.Name `
                -ErrorAction SilentlyContinue
        }

    }
    catch {
    }

    # ========================================================
    # 로그 Writer 닫기
    # ========================================================

    try {

        if ($null -ne $StdoutWriter) {
            $StdoutWriter.Close()
        }

    }
    catch {
    }

    try {

        if ($null -ne $StderrWriter) {
            $StderrWriter.Close()
        }

    }
    catch {
    }
}

Write-Host ""
Read-Host "Press Enter"