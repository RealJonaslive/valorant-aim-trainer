<#
  Baut "dist\Valorant Aim Trainer\Valorant Aim Trainer.exe" mit Nuitka.

  Warum Nuitka statt PyInstaller: Nuitka übersetzt den Python-Code in C und kompiliert
  eine normale Windows-.exe. Das generische PyInstaller-Startprogramm, das auch viele
  Schadprogramme benutzen, fällt weg -> deutlich weniger Fehlalarme bei Virenscannern.
  Dazu kommen vollständige Dateiinformationen (Hersteller, Produkt, Version).

      .\build_exe.ps1 1.0.1
#>
param([Parameter(Mandatory = $true)][string]$Version)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$out = "build\nuitka"
python -m nuitka main.py `
    --standalone `
    --assume-yes-for-downloads `
    --windows-console-mode=disable `
    --windows-icon-from-ico=assets\icon.ico `
    --include-data-files=assets\icon.png=assets\icon.png `
    --nofollow-import-to=tkinter --nofollow-import-to=unittest --nofollow-import-to=pydoc `
    --output-dir=$out `
    --output-filename="Valorant Aim Trainer.exe" `
    --company-name="RealJonaslive" `
    --product-name="Valorant Aim Trainer" `
    --file-description="Valorant Aim Trainer - Aim-Training und Sens-Analyse" `
    --file-version=$Version --product-version=$Version `
    --copyright="(c) RealJonaslive - Fan-Projekt, nicht mit Riot Games verbunden"
if ($LASTEXITCODE -ne 0) { throw "Nuitka-Build fehlgeschlagen (Exit $LASTEXITCODE)." }

$target = "dist\Valorant Aim Trainer"
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
New-Item -ItemType Directory -Force dist | Out-Null
Move-Item "$out\main.dist" $target
Write-Host "Gebaut: $target\Valorant Aim Trainer.exe" -ForegroundColor Green
