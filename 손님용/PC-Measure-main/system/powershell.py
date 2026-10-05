"""PowerShell command execution with explicit normal/admin selection."""
import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import config

def run(command, privilege='normal', timeout=60):
    if not isinstance(command,str) or not command.strip():
        raise ValueError('명령이 필요합니다.')
    if privilege not in ('normal','admin'):
        raise ValueError('권한은 normal 또는 admin입니다.')
    timeout = int(timeout)
    if not 1 <= timeout <= 600:
        raise ValueError('제한 시간은 1~600초입니다.')
    admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    if privilege == 'normal' and admin:
        raise PermissionError('현재 서버가 관리자 권한입니다. 일반 실행 바로가기로 다시 시작하세요.')
    normal_script = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; try { & { " + command + "\n }; if(-not $?) { exit 1 }; if($LASTEXITCODE) { exit $LASTEXITCODE } } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
    encoded = base64.b64encode(normal_script.encode('utf-16-le')).decode('ascii')
    flags = subprocess.CREATE_NO_WINDOW
    if privilege == 'normal' or admin:
        child = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
            capture_output=True, timeout=timeout, creationflags=flags)
        return {'success':child.returncode == 0, 'exit_code':child.returncode, 'privilege':privilege,
                'stdout':child.stdout.decode('utf-8',errors='replace'), 'stderr':child.stderr.decode('utf-8',errors='replace')}
    # UAC remains visible to the PC owner. The elevated process writes its own result.
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='powershell-',dir=config.PRIVATE) as directory:
        output = Path(directory)/'result.json'
        quoted = str(output).replace("'", "''")
        wrapper = "$ErrorActionPreference='Stop'; try { $global:LASTEXITCODE=0; $o=(& { " + command + "\n } 2>&1 | Out-String); $code=if($?){$LASTEXITCODE}else{1}; @{stdout=$o;exit_code=$code;success=($code -eq 0)} | ConvertTo-Json -Compress | Set-Content -LiteralPath '" + quoted + "' -Encoding UTF8 } catch { @{stdout='';stderr=$_.Exception.Message;exit_code=1;success=$false} | ConvertTo-Json -Compress | Set-Content -LiteralPath '" + quoted + "' -Encoding UTF8 }"
        admin_encoded = base64.b64encode(wrapper.encode('utf-16-le')).decode('ascii')
        launch = "$ErrorActionPreference='Stop'; $p=Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile','-NonInteractive','-EncodedCommand','" + admin_encoded + "' -PassThru; if(-not $p.WaitForExit(" + str(timeout*1000) + ")) { throw '관리자 명령 제한 시간 초과: 명령이 계속 실행될 수 있습니다. 자동 재시도하지 마세요.' }"
        child = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',launch],capture_output=True,timeout=timeout+30,creationflags=flags)
        if not output.exists():
            raise PermissionError('관리자 실행이 완료되지 않았습니다. UAC 거절 또는 시간 초과를 확인하세요.')
        return json.loads(output.read_text(encoding='utf-8-sig')) | {'privilege':'admin'}
