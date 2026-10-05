$ErrorActionPreference='Stop'
Start-Process -FilePath (Join-Path $PSScriptRoot 'PC-Measure.exe') -Verb RunAs
