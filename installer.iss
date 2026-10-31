; Setup für den Valorant Aim Trainer (Inno Setup 6).
; Wird von release.ps1 aufgerufen:  ISCC.exe /DAppVersion=1.2.3 installer.iss
;
; - Installiert pro Benutzer (kein Admin nötig) nach %LOCALAPPDATA%\Programs\Valorant Aim Trainer
; - AppId bleibt immer gleich -> neue Setups installieren ÜBER die alte Version (= Update)
; - Einstellungen/Runden liegen in %APPDATA%\ValorantAimTrainer und werden nicht angefasst
; - Bei stillem Update (/VERYSILENT, vom Programm selbst gestartet) wird das Programm danach neu gestartet

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Valorant Aim Trainer"
#define AppExe "Valorant Aim Trainer.exe"

[Setup]
AppId={{5643BE1A-E747-4F42-825E-7095D26118EA}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=RealJonaslive
AppPublisherURL=https://github.com/RealJonaslive/valorant-aim-trainer
AppSupportURL=https://github.com/RealJonaslive/valorant-aim-trainer/issues
; Dateiinformationen der Setup.exe (Rechtsklick -> Eigenschaften -> Details)
VersionInfoVersion={#AppVersion}
VersionInfoCompany=RealJonaslive
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=(c) RealJonaslive - Fan-Projekt, nicht mit Riot Games verbunden
DefaultDirName={localappdata}\Programs\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=ValorantAimTrainer-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Verknüpfungen:"

[InstallDelete]
; alte Bibliotheken entfernen, damit nach Updates keine Reste liegen bleiben
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; normale Installation: Häkchen "Jetzt starten" auf der letzten Seite
Filename: "{app}\{#AppExe}"; Description: "{#AppName} jetzt starten"; Flags: nowait postinstall skipifsilent
; Update im Hintergrund: Programm danach automatisch wieder starten
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: WizardSilent
