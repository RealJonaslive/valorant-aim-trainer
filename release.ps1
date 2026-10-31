<#
  Neue Version veröffentlichen - alles in einem Schritt:

      .\release.ps1 1.0.1 "Neuer Modus X; Fehler Y behoben"

  1. Versionsnummer in aimtrainer/version.py setzen
  2. Tests ausführen (bei Fehlern wird abgebrochen)
  3. .exe bauen (PyInstaller) und Setup bauen (Inno Setup)
  4. Code committen, Tag v<Version> setzen, zu GitHub hochladen
  5. GitHub-Release mit der Setup.exe anlegen
  -> Beim nächsten Start bekommen alle Freunde das Update (Pflicht-Update).
#>
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Notes = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version muss so aussehen: 1.2.3" }
$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) { $gh = "C:\Program Files\GitHub CLI\gh.exe" }
$iscc = Get-ChildItem "$env:LOCALAPPDATA\Programs\Inno Setup*\ISCC.exe", "C:\Program Files*\Inno Setup*\ISCC.exe" `
        -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $iscc) { throw "Inno Setup (ISCC.exe) nicht gefunden." }

function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what fehlgeschlagen (Exit $LASTEXITCODE)." } }

Write-Host "== Version $Version ==" -ForegroundColor Cyan
$vf = "aimtrainer\version.py"
(Get-Content $vf -Raw -Encoding UTF8) -replace '__version__ = "[^"]*"', "__version__ = `"$Version`"" |
    Set-Content $vf -Encoding UTF8 -NoNewline

Write-Host "== Tests ==" -ForegroundColor Cyan
python tests\test_aimtrainer.py | Out-Null; Check "Tests"

Write-Host "== .exe bauen ==" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --windowed --name "Valorant Aim Trainer" --icon assets\icon.ico `
    --add-data "assets\icon.png;assets" --exclude-module tkinter --distpath dist --workpath build main.py | Out-Null
Check "PyInstaller"

Write-Host "== Setup bauen ==" -ForegroundColor Cyan
& $iscc /Q "/DAppVersion=$Version" installer.iss; Check "Inno Setup"
$setup = "release\ValorantAimTrainer-Setup-$Version.exe"

Write-Host "== Zu GitHub hochladen ==" -ForegroundColor Cyan
git add -A
if (git status --porcelain) { git commit -m "Version $Version" | Out-Null; Check "git commit" }
git tag "v$Version"; Check "git tag"
git push origin HEAD --tags; Check "git push"
if ($Notes) { & $gh release create "v$Version" $setup --title "Version $Version" --notes $Notes }
else { & $gh release create "v$Version" $setup --title "Version $Version" --generate-notes }
Check "GitHub-Release"

Write-Host "Fertig: Version $Version ist veröffentlicht." -ForegroundColor Green
