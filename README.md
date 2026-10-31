# Valorant Aim Trainer

Aim-Training mit exakt demselben Mausgefühl wie in Valorant – und einer Auswertung, die dir deine
passende Empfindlichkeit (Sens) vorschlägt.

## Installation (für Spieler)

1. Rechts auf dieser Seite unter **Releases** die neueste Version öffnen.
2. **`ValorantAimTrainer-Setup-x.y.z.exe`** herunterladen und starten.
3. Windows zeigt eventuell „Der Computer wurde durch Windows geschützt“ – das kommt, weil das
   Programm nicht kostenpflichtig signiert ist. Auf **„Weitere Informationen“ → „Trotzdem ausführen“** klicken.
4. Setup durchklicken – fertig. Auf dem Desktop liegt jetzt „Valorant Aim Trainer“.

**Updates:** Beim Start prüft das Programm automatisch, ob es eine neue Version gibt. Wenn ja, muss
sie installiert werden („Jetzt aktualisieren“) – das geht automatisch, danach startet das Programm neu.
Deine Einstellungen und Runden bleiben dabei erhalten (gespeichert in `%APPDATA%\ValorantAimTrainer`).

Deinstallieren: Windows-Einstellungen → Apps → „Valorant Aim Trainer“.

## About (English)

Valorant Aim Trainer is a free, open-source aim trainer for Windows. It reproduces Valorant's exact
mouse-to-camera math (0.07° per count × sensitivity, 103° horizontal FOV, raw mouse input) and offers
four training modes (Flick, Multi-Bot, Tracking, Peek with movement and cover). Every shot and mouse
movement is analysed (reaction time, overshoot/undershoot, click timing) to recommend a sensitivity,
per round and across all rounds. Crosshairs can be imported/exported as Valorant profile codes.
Installer with uninstaller; updates are delivered via GitHub Releases.

## Privacy

The program stores settings and training results only locally in `%APPDATA%\ValorantAimTrainer`.
It does not collect or send any personal data. The only network access is the update check at start:
it requests the latest release information from the GitHub API
(`api.github.com/repos/RealJonaslive/valorant-aim-trainer/releases/latest`) and, if a newer version
exists and the user clicks "Jetzt aktualisieren", downloads the installer from GitHub. GitHub's
[privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) applies to these requests.

## Code signing policy

Code signing via the [SignPath Foundation](https://signpath.org) is being prepared (not active yet).
All release binaries are built from this repository by GitHub Actions
([build.yml](.github/workflows/build.yml)); nothing is built or uploaded by hand.

- Committers and reviewers: [RealJonaslive](https://github.com/RealJonaslive)
- Approvers: [RealJonaslive](https://github.com/RealJonaslive)
- Privacy policy: see [Privacy](#privacy) above.

## License

[MIT](LICENSE). Bundled third-party components: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
"Valorant" is a trademark of Riot Games, Inc. This fan project is not affiliated with or endorsed by Riot Games.

---

## Für Entwickler

Neue Version veröffentlichen: Version hochzählen, testen, Code + Tag hochladen. GitHub Actions baut
daraus .exe + Setup und legt das Release an (Fortschritt unter „Actions“ auf GitHub):

```
.\release.ps1 1.0.2 "Was ist neu"
.\release.ps1 1.0.2 "Was ist neu" -Local    # Notfall: lokal bauen und hochladen
```

Start aus dem Quellcode per Doppelklick auf **„Valorant Aim Trainer“** auf dem Desktop (startet `main.py` mit
`pythonw.exe`, ohne Konsolenfenster; Fehler landen dann in `fehler.log`). Icon: `assets/icon.ico`.

```
pip install -r requirements.txt
python main.py              # normales Fenster: verschieben, minimieren, maximieren, Größe ziehen
python main.py --fullscreen # exklusives Vollbild
python analyze.py           # alle Sessions gemeinsam auswerten
python tests/test_aimtrainer.py
```

Menü (per Maus) mit vier Tabs:
- **Training**: Sens, DPI, Dauer eintragen, Modus-Karte anklicken, START (oder ENTER).
- **Fadenkreuz**: Farbe, Outline, Center Dot, innere/äußere Linien (Deckkraft, Länge, Dicke, Abstand),
  „Beim Schießen rot“ – mit Live-Vorschau. Wird in `config.json` gespeichert.
- **Anleitung**: Steuerung und Ablauf.
- **Ergebnis**: Analyse der letzten Runde, „Empfehlung übernehmen“ trägt die neue Sens ein.

Im Training: linke Maustaste = Schießen (Fadenkreuz wird kurz rot). Ziele sind Übungs-Bots;
Kopftreffer = Kill (Bot sackt zusammen), Körpertreffer = kein Kill. Jede Session landet als
`.json` + `.txt` in `sessions/`.

Während des Trainings ist die Maus im Fenster gefangen (wie in Valorant). Alt-Tab oder die
Windows-Taste pausiert die Runde und gibt die Maus frei – dann kannst du das Fenster verschieben,
minimieren usw. Klick ins Fenster setzt fort; die Pausenzeit zählt nicht zur Rundendauer.
Bei jeder Größenänderung wird der 16:9-Viewport mit 103° neu berechnet.

---

## 1. Die Mathematik

### Rotation pro Count
Valorant (UE4) verarbeitet Mausbewegung **linear, ohne Beschleunigung, ohne Smoothing**:

```
Δyaw   [°] =  counts_x · sens · 0.07
Δpitch [°] = −counts_y · sens · 0.07
```

`0.07` ist Valorants fester Yaw-Multiplikator (Pitch identisch). Daraus:

| Größe | Formel | Beispiel 0.35 @ 800 DPI |
|---|---|---|
| Grad pro Count | `0.07 · sens` | 0.0245° |
| eDPI | `sens · DPI` | 280 |
| cm/360 | `360 / (0.07 · sens · DPI) · 2.54` | 46.65 cm |
| Sens aus cm/360 | `360 · 2.54 / (0.07 · DPI · cm)` | – |

Ein *Count* ist ein Sensor-Schritt der Maus; bei 800 DPI sind das 800 Counts pro Zoll Mausweg.
Damit sich das Programm 1:1 anfühlt, braucht es nur zwei Dinge: **dieselben rohen Counts** (Raw Input)
und **denselben Faktor** (0.07 · sens) – genau das macht `Camera.apply_counts()`. Yaw wird in
float64 akkumuliert und nie gerundet, es gehen also keine Teil-Counts verloren.

### FOV
Die FOV beeinflusst die Rotation **nicht** – nur, wie groß die Welt auf dem Bildschirm aussieht.
Valorant hat fest **103° horizontal bei 16:9**:

```
vFOV = 2 · atan( tan(103°/2) / (16/9) ) ≈ 70.53°
f_px = (Breite/2) / tan(103°/2)          # Brennweite in Pixeln
x_screen = cx + f_px · x_cam / z_cam
y_screen = cy − f_px · y_cam / z_cam
```

Gleiche Brennweite für x und y = quadratische Pixel. Andere Seitenverhältnisse (16:10, Ultrawide)
werden wie in Valorant auf einen 16:9-Viewport gelettert, damit Zielgrößen und „Pixel pro Grad“
identisch zum Spiel sind.

### Raw Input
`aimtrainer/raw_input.py` registriert über die Win32-API (`RegisterRawInputDevices`, `WM_INPUT`)
ein unsichtbares Fenster für die Maus. Die Counts kommen **vor** Windows-Zeigerbeschleunigung
und Zeigergeschwindigkeit an – wie in Valorant. Jedes Event bekommt einen `perf_counter`-Zeitstempel
und wird in Originalreihenfolge verarbeitet: ein Klick wird mit der Blickrichtung **genau in diesem
Moment** ausgewertet, nicht erst am Frame-Ende.
SDL wird per `SDL_MOUSE_RELATIVE_MODE_WARP=1` daran gehindert, eine eigene Raw-Input-Registrierung
zu machen (Windows erlaubt nur ein Ziel pro Prozess und Gerätetyp).

---

## 2. Architektur

```
main.py / analyze.py
aimtrainer/
  valorant_math.py   Formeln (Sens, cm/360, FOV)            – reine Funktionen, getestet
  raw_input.py       Win32 Raw Input Thread → Event-Queue
  camera.py          Yaw/Pitch, Basisvektoren, Ray-Kugel-Treffertest, Fehlerwinkel
  modes.py           Flick / Gridshot / Tracking  → zeichnen Trials & Samples auf
  renderer.py        Perspektivprojektion 103°, Frustum-Clipping, Crosshair
  analysis.py        Signalverarbeitung, Metriken, Sens-Empfehlung, Report
  app.py             Menü (Eingabefelder) → Training → Analyse → Speichern
tests/               Simulierter Spieler mit bekanntem Over-/Undershoot
```

Datenfluss pro Frame:
`RawMouse.drain()` → für jedes Event `cam.apply_counts()` + `mode.on_input(t)` (Sample) bzw.
`mode.on_click(t)` → `mode.update()` (Spawns, Bewegung) → `renderer` (~0.8 ms/Frame).

Aufzeichnung: Pro Ziel ein **Trial** mit Samples `[t, Fehler_yaw, Fehler_pitch]` (Ziel − Fadenkreuz,
in Grad, Yaw mit cos(pitch) auf echten Bildschirmwinkel skaliert) bei **jedem** Raw-Event
(bei 1000 Hz Polling = 1000 Samples/s) plus alle Klicks mit Treffer/Fehlschuss.

### Trainingsmodi
| Modus | Aufbau | Misst vor allem |
|---|---|---|
| **Flick** | Ein Bot erscheint nach zufälliger Pause (0.35–0.9 s, keine Antizipation) 4–30° neben dem Fadenkreuz in 8–30 m. Kopfschuss = Kill. | Primär-Gain (Over/Undershoot), Reaktionszeit, Klick-Timing |
| **Multi-Bot** | 3 Bots gleichzeitig (5 Spalten × 8/12/16 m), Kill → neuer Bot. | Flick-Ketten, Zielwechsel, Fehlklicks |
| **Tracking** | Bot strafet ADAD mit 6.75 m/s (Valorant-Laufgeschwindigkeit) in 12 m, zufällige Wechsel & Stopps. | Velocity-Gain, Lag, Jitter, Reaktion auf Richtungswechsel |
| **Peek** | Du läufst mit WASD (6.75 m/s) durch eine Arena mit zufällig platzierten Kisten (`world.py`). 2 Bots verstecken sich hinter hohen Kisten und peeken zufällig: Seite, Weite (40 % knapp an der Kante, 40 % normal, 20 % weiter Swing), Tempo, Haltezeit, 25 % Jiggle-Peeks. Versteck/Peek-Punkt werden bei jedem Peek relativ zu deiner aktuellen Position berechnet. Kisten blockieren Schüsse; über 1.35 m/s streuen Schüsse bis 4° (Counter-Strafe nötig, Näherung an Valorant). | Zeit vom Auftauchen bis Kill, Zeit bis erster Schuss, Crosshair-Placement beim Auftauchen, Headshot-Quote, Schüsse in Bewegung (keine Sens-Empfehlung) |

Bots (`bots.py`): Körper aus gedrehten Boxen (immer zur Kamera), Kopf als Kugel r = 0.115 m auf
~1.6 m (Augenhöhe) – auf 10 m ≈ 0.66° Radius. Treffer per Raycast; der nächste getroffene Teil
zählt (Kopf oder Körper). Maße sind Näherungen und als Konstanten anpassbar.

---

## 3. Analyse & Sens-Rechner (`analysis.py`)

**Flick-Zerlegung** (Optimized-Submovement-Modell): Jeder Flick = schnelle ballistische
Primärbewegung + Korrekturen. Die Primärbewegung kommt rein aus dem Muskelgedächtnis – sie zeigt,
ob Sens und Handkalibrierung zusammenpassen.

1. Samples auf 1 kHz resamplen, Fadenkreuz-Weg auf die Richtung zum Ziel projizieren.
2. Geschwindigkeit glätten (Dreiecksfilter), Peak finden.
3. Reaktionszeit = Beginn (v > 10 % v_peak). Primär-Ende = erster Punkt nach dem Peak mit v < 8 % v_peak.
4. `gain = Weg_am_Primär-Ende / Winkel_zum_Ziel` → > 1 Overshoot, < 1 Undershoot.
5. Zusätzlich: max. Overshoot, seitlicher Fehler, Anzahl Korrekturen, Fehlklicks vor/hinter dem Ziel,
   Fadenkreuz-Speed beim Klick, Verweilzeit auf dem Ziel vor dem Klick.

**Empfehlung:** Winkel = Handweg · sens · 0.07 ⇒ die Korrektur ist multiplikativ:

```
sens_neu = sens_alt · gain_ziel / median(gain)
```

- `gain_ziel = 0.97`: Menschen landen bei schnellen Zielbewegungen natürlicherweise knapp *vor* dem Ziel.
- Robust: Median im Log-Raum, MAD-Ausreißerfilter (3σ), 95 %-Bootstrap-Konfidenzintervall.
- Tracking: `velocity_gain = Fadenkreuz-/Zielgeschwindigkeit` in stabilen Strafe-Phasen; fließt mit 30 % ein.
- Dämpfung `n/(n+15)` und breites Konfidenzintervall senken das Vertrauen; max. ±10 % pro Session,
  unter 1.5 % Abweichung → „nicht ändern“.
- Diagnosen, die **keine** Sens-Frage sind, werden separat gemeldet: Range-Effekt (kurze Flicks zu weit,
  lange zu kurz), Links/Rechts-Asymmetrie, hoher Tracking-Jitter, Zögern vor dem Klick.

**Ehrliche Einordnung:** Es gibt keine objektiv „perfekte“ Sens – das Gehirn kalibriert sich auf jede
Sens um. Das Programm findet die Sens, bei der deine *aktuelle* Motorik am saubersten landet. Am
aussagekräftigsten: mehrere Sessions (`analyze.py`), aufgewärmt, und Empfehlungen in kleinen Schritten
übernehmen statt große Sprünge zu machen.
