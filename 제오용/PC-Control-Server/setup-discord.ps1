$taskPython = (Get-Command pythonw).Source
Start-Process -FilePath $taskPython -ArgumentList (Join-Path $PSScriptRoot 'setup_discord.py') -WindowStyle Hidden
