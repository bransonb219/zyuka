# Zyuka Windows dogfood script
# Run in a fresh PowerShell window. Each step prints a header; pause and note
# anything odd before moving to the next.
#
# Prerequisites: Python 3.11+ and pipx installed.
#   python --version
#   pipx --version
# If pipx is missing:
#   python -m pip install --user pipx
#   python -m pipx ensurepath
#   (restart the shell so PATH picks up the pipx bin dir)

$ErrorActionPreference = "Stop"

function Step($n, $title) {
    Write-Host ""
    Write-Host "=== Step $n — $title ===" -ForegroundColor Cyan
}

$WheelUrl = "https://github.com/bransonb219/zyuka/releases/download/v0.1.0/zyuka-0.1.0-py3-none-any.whl"
$DogfoodDir = Join-Path $env:USERPROFILE "zyuka-dogfood"

Step 1 "Install zyuka via pipx (from GitHub release wheel)"
# Uninstall first so we start clean
pipx uninstall zyuka 2>$null
pipx install $WheelUrl
zyuka --version

Step 2 "Run demo end-to-end"
if (Test-Path $DogfoodDir) { Remove-Item -Recurse -Force $DogfoodDir }
New-Item -ItemType Directory -Path $DogfoodDir | Out-Null
Set-Location $DogfoodDir
zyuka demo --open
Write-Host "Demo outputs:" -ForegroundColor Yellow
Get-ChildItem -Recurse zyuka-demo | Select-Object FullName, Length

Step 3 "Run init wizard in a fresh folder"
$InitDir = Join-Path $DogfoodDir "init-test"
New-Item -ItemType Directory -Path $InitDir | Out-Null
Set-Location $InitDir
Write-Host "Follow the prompts; place the key OUTSIDE this folder." -ForegroundColor Yellow
zyuka init
Write-Host "Files written:" -ForegroundColor Yellow
Get-ChildItem

Step 4 "Launch GUI"
Set-Location $DogfoodDir
Write-Host "Browser should open at http://127.0.0.1:8501 (or similar)." -ForegroundColor Yellow
Write-Host "Try: Upload & Quality, Privacy Scan, Reports. Ctrl+C to stop." -ForegroundColor Yellow
zyuka gui

Write-Host ""
Write-Host "Dogfood complete. Note findings in the chat." -ForegroundColor Green
