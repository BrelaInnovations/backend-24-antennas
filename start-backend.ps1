param([switch]$Setup, [switch]$Mongo)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if ($Setup -or -not (Test-Path $pythonExe)) {
    if (-not (Test-Path $pythonExe)) {
        $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv }
        elseif (Test-Path $bundledPython) { & $bundledPython -m venv .venv }
        else { throw 'Install Python 3.11 or newer, then run this command again.' }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
    }
    & $pythonExe -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
$env:NAIBRA_STORAGE = if ($Mongo) { 'mongo' } else { 'sqlite' }
$env:HARDWARE_SIMULATE = 'false'
Write-Host 'NaiBra API: http://localhost:8001/docs (Ctrl+C to stop)'
& $pythonExe -m uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
exit $LASTEXITCODE

