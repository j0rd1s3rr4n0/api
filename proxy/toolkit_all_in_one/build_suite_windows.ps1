$ErrorActionPreference = "Stop"

$SuiteRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProxyRoot = Resolve-Path (Join-Path $SuiteRoot "..")
$Python = Join-Path $ProxyRoot "..\venv\Scripts\python.exe"
$Out = Join-Path $SuiteRoot "suite_dist"
$Tools = Join-Path $Out "tools"

if (!(Test-Path $Python)) {
    throw "No encuentro Python venv: $Python"
}

Remove-Item -LiteralPath $Out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Tools -Force | Out-Null

foreach ($name in @(
    "proxy_security_toolkit",
    "google_dork_auditor",
    "opendir_downloader",
    "opendir_downloader_gui",
    "opendir_downloader_pro",
    "ultimater_multi"
)) {
    Get-Process $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

function Build-Spec($WorkDir, $Spec) {
    Push-Location $WorkDir
    try {
        & $Python -m PyInstaller --clean $Spec
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller fallo con $Spec"
        }
    } finally {
        Pop-Location
    }
}

Build-Spec $ProxyRoot "ultimater_multi.spec"
Build-Spec (Join-Path $ProxyRoot "google_dork_auditor") "google_dork_auditor.spec"
Build-Spec (Join-Path $ProxyRoot "opendir_downloader") "opendir_downloader.spec"
Build-Spec (Join-Path $ProxyRoot "opendir_downloader") "opendir_downloader_gui.spec"
Build-Spec (Join-Path $ProxyRoot "opendir_downloader_pro") "opendir_downloader_pro.spec"
Build-Spec $SuiteRoot "toolkit_launcher.spec"

Copy-Item (Join-Path $SuiteRoot "dist\proxy_security_toolkit.exe") $Out -Force
Copy-Item (Join-Path $ProxyRoot "dist\ultimater_multi.exe") $Tools -Force
Copy-Item (Join-Path $ProxyRoot "google_dork_auditor\dist\google_dork_auditor.exe") $Tools -Force
Copy-Item (Join-Path $ProxyRoot "opendir_downloader\dist\opendir_downloader.exe") $Tools -Force
Copy-Item (Join-Path $ProxyRoot "opendir_downloader\dist\opendir_downloader_gui.exe") $Tools -Force
Copy-Item (Join-Path $ProxyRoot "opendir_downloader_pro\dist\opendir_downloader_pro.exe") $Tools -Force

Write-Host ""
Write-Host "[OK] Suite creada en:"
Write-Host "  $Out"
Write-Host ""
Get-ChildItem $Out, $Tools | Select-Object FullName, Length
