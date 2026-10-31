<#
  Neue Version veröffentlichen:

      .\release.ps1 1.0.2 "Was ist neu"

  1. Versionsnummer in aimtrainer/version.py setzen
  2. Tests ausführen (bei Fehlern wird abgebrochen)
  3. Code committen, Tag v<Version> (mit den Notizen) setzen und zu GitHub hochladen
  4. GitHub Actions (.github/workflows/build.yml) baut daraus nachprüfbar .exe + Setup
     und legt das Release an -> alle Freunde bekommen beim nächsten Start das Update.
     Fortschritt: https://github.com/RealJonaslive/valorant-aim-trainer/actions

  Notfall ohne GitHub Actions (lokal bauen und hochladen):
      .\release.ps1 1.0.2 "Was ist neu" -Local
#>
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Notes = "",
    [switch]$Local
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version muss so aussehen: 1.2.3" }
if (-not $Notes) { $Notes = "Version $Version" }
$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) { $gh = "C:\Program Files\GitHub CLI\gh.exe" }

function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what fehlgeschlagen (Exit $LASTEXITCODE)." } }

Write-Host "== Version $Version ==" -ForegroundColor Cyan
$vf = "aimtrainer\version.py"
(Get-Content $vf -Raw -Encoding UTF8) -replace '__version__ = "[^"]*"', "__version__ = `"$Version`"" |
    Set-Content $vf -Encoding UTF8 -NoNewline

Write-Host "== Tests ==" -ForegroundColor Cyan
python tests\test_aimtrainer.py | Out-Null; Check "Tests"

if ($Local) {
    $iscc = Get-ChildItem "$env:LOCALAPPDATA\Programs\Inno Setup*\ISCC.exe", "C:\Program Files*\Inno Setup*\ISCC.exe" `
            -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if (-not $iscc) { throw "Inno Setup (ISCC.exe) nicht gefunden." }
    Write-Host "== .exe bauen (Nuitka) ==" -ForegroundColor Cyan
    & "$PSScriptRoot\build_exe.ps1" $Version
    Write-Host "== Setup bauen ==" -ForegroundColor Cyan
    & $iscc /Q "/DAppVersion=$Version" installer.iss; Check "Inno Setup"
}

Write-Host "== Zu GitHub hochladen ==" -ForegroundColor Cyan
git add -A
if (git status --porcelain) { git commit -m "Version $Version" | Out-Null; Check "git commit" }
git tag -a "v$Version" -m $Notes; Check "git tag"
git push origin HEAD --follow-tags; Check "git push"

if ($Local) {
    & $gh release create "v$Version" "release\ValorantAimTrainer-Setup-$Version.exe" --title "Version $Version" --notes $Notes
    Check "GitHub-Release"
    Write-Host "Fertig: Version $Version ist veröffentlicht." -ForegroundColor Green
} else {
    Write-Host "Hochgeladen. GitHub baut jetzt das Setup und veröffentlicht Version $Version (ca. 10 Minuten):" -ForegroundColor Green
    Write-Host "https://github.com/RealJonaslive/valorant-aim-trainer/actions"
}
