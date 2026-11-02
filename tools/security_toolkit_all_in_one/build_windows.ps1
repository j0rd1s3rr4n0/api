$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot "..\..\venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

& $python -m py_compile .\security_toolkit_all_in_one.py
& $python -m PyInstaller --clean .\security_toolkit_all_in_one.spec
Write-Host "OK: dist\security_toolkit_all_in_one.exe"
