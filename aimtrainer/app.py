"""Hauptprogramm: Menü (Training / Fadenkreuz / Anleitung / Ergebnis) -> Training -> Analyse."""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# WICHTIG: vor pygame-Import. SDL soll im Relative-Mode den Cursor nur warpen und
# KEIN eigenes RegisterRawInputDevices machen - sonst ueberschreibt SDL unsere
# Raw-Input-Registrierung (pro Prozess gibt es nur ein Ziel pro Geraeteklasse).
os.environ["SDL_MOUSE_RELATIVE_MODE_WARP"] = "1"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from . import crosshair  # noqa: E402
from . import sessions  # noqa: E402
from . import ui  # noqa: E402
from . import livedraw  # noqa: E402
from .analysis import analyze_session, build_report  # noqa: E402
from .bots import Bot  # noqa: E402
from .camera import Camera  # noqa: E402
from .environment import Environment  # noqa: E402
from .modes import GENERAL_TIPS, MODE_INFO, MODE_TIPS, MODES  # noqa: E402
from .raw_input import RawMouse  # noqa: E402
from .renderer import Renderer  # noqa: E402
from .valorant_math import VALORANT_ASPECT, cm_per_360  # noqa: E402
from .world import BOUNDS  # noqa: E402
from . import updater  # noqa: E402
from .paths import CONFIG, DATA_DIR, FROZEN, ICON, SESSIONS  # noqa: E402
from .version import __version__  # noqa: E402

FIRE_FLASH = 0.10        # so lange bleibt das Fadenkreuz nach einem Klick rot [s]
STATIC_ARENA = (-40.0, 40.0, -40.0, 40.0)   # Arena fuer Modi ohne Bewegung
CONTENT_W = 1180         # maximale Inhaltsbreite im Menü
TOP = 140                # Oberkante des Inhaltsbereichs
PREVIEW_H = 150          # Höhe der Fadenkreuz-Vorschau
ALL = "ALL"              # Auswahl "Gesamtbilanz" im Tab Ergebnisse

TABS = [("training", "Training"), ("crosshair", "Fadenkreuz"), ("help", "Anleitung"), ("result", "Ergebnisse")]

HELP = [
    ("Was macht dieses Programm?",
     "Hier übst du das Zielen für Valorant. Die Maus fühlt sich genau so an wie im Spiel.\n"
     "Während du spielst, merkt sich das Programm jede Bewegung und jeden Schuss. Am Ende sagt es dir, "
     "ob deine Maus-Empfindlichkeit gut zu dir passt – oder ob du sie etwas höher oder niedriger "
     "stellen solltest."),
    ("Los geht's – in 4 Schritten",
     "1.  Öffne den Tab „Training“.\n"
     "2.  Trage deine Empfindlichkeit aus Valorant ein. Du findest sie im Spiel unter "
     "Einstellungen → Allgemein → Maus → „Empfindlichkeit: Zielen“ (zum Beispiel 0.35).\n"
     "3.  Trage die DPI deiner Maus ein. Die steht in der Software deiner Maus (z. B. Logitech G HUB "
     "oder Razer Synapse) oder auf der Verpackung. Weißt du es nicht? Dann probier 800 – das ist sehr häufig.\n"
     "4.  Wähle einen Modus aus und klicke auf START (oder drücke Enter)."),
    ("So spielst du",
     "•  Maus bewegen = umschauen und zielen\n"
     "•  Linke Maustaste = schießen (das Fadenkreuz in der Mitte wird kurz rot)\n"
     "•  Ziele auf den gelben Kopf der Figuren. Triffst du den Kopf, fällt die Figur um.\n"
     "•  Ein Treffer am Körper zählt nicht – die Figur blinkt nur kurz weiß.\n"
     "•  Nur im Modus „Peek“: Mit W A S D läufst du herum (W vor, S zurück, A links, D rechts)."),
    ("Dein eigenes Fadenkreuz",
     "Im Tab „Fadenkreuz“ stellst du Farbe, Linien und Punkt ein – rechts siehst du sofort die Vorschau.\n"
     "Fadenkreuz aus Valorant übernehmen: In Valorant unter Einstellungen → Fadenkreuz dein Profil "
     "exportieren (der Code wird kopiert). Dann hier ins Feld „Valorant-Profilcode“ klicken, Strg+V "
     "drücken und auf „Importieren“ klicken.\n"
     "Umgekehrt geht's auch: „Code kopieren“ und den Code in Valorant als Profil importieren.\n"
     "Mit „Als Profil speichern“ legst du mehrere Fadenkreuze an und wechselst per Klick zwischen ihnen."),
    ("Pause und Beenden",
     "•  Drück Esc: Das Spiel hält an und ein Pausenmenü erscheint. Dort wählst du "
     "„Weiterspielen“ oder „Beenden und Auswertung ansehen“.\n"
     "•  Noch einmal Esc drücken geht auch – dann spielst du einfach weiter.\n"
     "•  Alt+Tab oder Windows-Taste: Das Spiel pausiert ebenfalls und du kannst die Maus frei bewegen.\n"
     "•  Die Zeit läuft in der Pause nicht weiter.\n"
     "•  Das Fenster kannst du jederzeit verschieben, groß machen oder verkleinern – das Pausenmenü "
     "bleibt dabei immer fest in der Mitte des Programms."),
    ("Die vier Modi",
     "Flick: Eine Figur taucht plötzlich neben dir auf. Zieh die Maus schnell auf ihren Kopf und klick. "
     "Dieser Modus ist am besten, um deine Empfindlichkeit zu prüfen.\n"
     "Multi-Bot: Drei Figuren stehen nebeneinander. Schieß sie nacheinander ab – es kommen immer neue.\n"
     "Tracking: Eine Figur läuft hin und her. Halte das Fadenkreuz die ganze Zeit auf ihrem Kopf.\n"
     "Peek: Du läufst durch eine Arena mit Kisten. Figuren verstecken sich dahinter und schauen "
     "plötzlich heraus – mal nur ein kleines Stück, mal weit. Bleib zum Schießen stehen, denn im "
     "Laufen gehen deine Schüsse daneben (genau wie in Valorant)."),
    ("Deine Ergebnisse",
     "Nach jeder Runde öffnet sich der Tab „Ergebnisse“. Links siehst du alle Runden, die du je gespielt "
     "hast – die neueste steht oben. Klick eine Runde an, um rechts alle Details zu sehen.\n"
     "Ganz oben im gelben Kasten steht die empfohlene Empfindlichkeit. Mit „Diese Empfehlung übernehmen“ "
     "wird sie für die nächste Runde eingetragen. Gefällt sie dir, stell sie auch in Valorant ein.\n"
     "Ganz oben in der Liste steht die „Gesamtbilanz“: Sie wertet ALLE Runden zusammen aus und ist die "
     "verlässlichste Empfehlung. Neuere Runden zählen stärker. Ein Diagramm zeigt, welche Sens in jeder "
     "Runde ideal gewesen wäre."),
    ("Begriffe einfach erklärt",
     "Sens (Empfindlichkeit): wie weit sich dein Blick dreht, wenn du die Maus bewegst. Höher = schneller.\n"
     "DPI: wie fein deine Maus misst. Zusammen mit der Sens ergibt sich, wie schnell sich alles anfühlt.\n"
     "eDPI: Sens × DPI – eine Zahl, mit der man Einstellungen von Spielern vergleichen kann.\n"
     "cm/360°: so viele Zentimeter musst du die Maus schieben, um dich einmal ganz im Kreis zu drehen.\n"
     "Overshoot (zu weit): Du ziehst über den Kopf hinaus. Passiert das oft, ist die Sens eher zu hoch.\n"
     "Undershoot (zu kurz): Du hörst vor dem Kopf auf. Passiert das oft, ist die Sens eher zu niedrig.\n"
     "Reaktionszeit: wie schnell du anfängst, die Maus zu bewegen, nachdem ein Ziel auftaucht.\n"
     "Flick: eine schnelle Mausbewegung auf ein Ziel.   Peek: kurz hinter einer Deckung hervorschauen.\n"
     "Counter-Strafe: kurz in die Gegenrichtung tippen, um sofort stehen zu bleiben und genau zu schießen."),
    ("Tipps für gute Ergebnisse",
     "•  Spiel dich erst ein paar Minuten warm, bevor du auf die Empfehlung achtest.\n"
     "•  Spiel mehrere Flick-Runden. Je mehr Runden, desto genauer die Empfehlung.\n"
     "•  Ändere deine Sens immer nur in kleinen Schritten und gib dir ein paar Tage Zeit, dich daran "
     "zu gewöhnen.\n"
     "•  Sagt das Programm „passt“, ist deine Sens in Ordnung – dann hilft vor allem weiter üben."),
]


def load_config():
    cfg = {"sens": "0.35", "dpi": "800", "mode": "flick", "duration": "60"}
    try:
        cfg.update(json.loads(CONFIG.read_text("utf-8")))
    except (OSError, ValueError):
        pass
    cfg["crosshair"] = crosshair.merged(cfg.get("crosshair"))
    cfg.setdefault("crosshair_profiles", [])   # [{"name": ..., "code": Valorant-Profilcode}]
    cfg.setdefault("crosshair_active", None)
    return cfg


def viewport_rect(w, h):
    """Valorant rendert 103 Grad hFOV auf 16:9; andere Seitenverhaeltnisse -> Letterbox."""
    if w / h > VALORANT_ASPECT:
        vw = int(h * VALORANT_ASPECT)
        return pygame.Rect((w - vw) // 2, 0, vw, h)
    vh = int(w / VALORANT_ASPECT)
    return pygame.Rect(0, (h - vh) // 2, w, vh)


def report_sections(report):
    """Report-Zeilen -> (Kopfzeilen, Hauptergebnis, [(Titel, Zeilen)])."""
    head, best, sections = [], None, []
    for line in report[1:]:
        if not line:
            continue
        if line.startswith("-- "):
            sections.append((line.strip("- "), []))
        elif line.startswith(">>> "):
            best = line[4:]
        elif sections:
            sections[-1][1].append(line)
        else:
            head.append(line)
    return head, best, sections


class App:
    def __init__(self, fullscreen=False):
        if sys.platform == "win32":
            # Eigene App-ID: sonst gruppiert Windows das Fenster unter python.exe und zeigt
            # in der Taskleiste das Python-Symbol statt unseres Icons.
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ValorantAimTrainer.App")
            except (AttributeError, OSError):
                pass
        pygame.init()
        if ICON.exists():
            pygame.display.set_icon(pygame.transform.smoothscale(pygame.image.load(str(ICON)), (256, 256)))
        # Standard: normales Windows-Fenster (verschieben, minimieren, maximieren, schliessen,
        # Groesse am Rand ziehen). --fullscreen fuer exklusives Vollbild.
        flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
        size = (0, 0) if fullscreen else (1280, 780)
        pygame.display.set_mode(size, flags, vsync=0)
        pygame.display.set_caption("Valorant Aim Trainer")
        self._layout()
        livedraw.install()   # Bild auch während Fenster-Ziehen/Größe-Ändern aktualisieren
        self.fonts = ui.Fonts()
        self.st = ui.UIState()
        self.raw = RawMouse()
        self.raw_ok = self.raw.start()
        self.cfg = load_config()
        self.env_static = Environment(STATIC_ARENA)
        self.tab = "training"
        self.help_scroll = 0
        self.form = {"xcode": ""}    # Eingabefeld für Fadenkreuz-Codes
        self.xstatus = ("", ui.GOOD)
        self.profile_scroll = 0
        self.history = None          # gespeicherte Runden (wird beim Öffnen des Tabs geladen)
        self.overall = None          # Gesamtbilanz aus allen Runden
        self.selected = None
        self.list_scroll = 0
        self.detail_scroll = 0
        self.detail_max = 0
        self.report = []
        self.last_rec = None
        self.start_requested = False
        self.clock = pygame.time.Clock()

    def _layout(self):
        """Nach jeder Groessenaenderung: 16:9-Viewport und Projektion neu berechnen."""
        self.screen = pygame.display.get_surface()
        self.view = self.screen.subsurface(viewport_rect(*self.screen.get_size()))
        self.r = Renderer(self.view)
        self._preview = None
        self._layout_size = self.screen.get_size()

    def _sync_layout(self):
        """Fenstergröße hat sich geändert (auch mitten im Ziehen) -> Layout neu."""
        if pygame.display.get_surface().get_size() != self._layout_size:
            self._layout()

    def _frame(self):
        """Linker Rand und Breite des zentrierten Inhaltsbereichs."""
        w = self.screen.get_width()
        cw = min(CONTENT_W, w - 60)
        return (w - cw) // 2, cw

    def _save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(self.cfg, indent=2, ensure_ascii=False), "utf-8")
        except OSError:
            pass

    def _valid(self):
        try:
            return float(self.cfg["sens"]) > 0 and float(self.cfg["dpi"]) > 0 and float(self.cfg["duration"]) > 0
        except ValueError:
            return False

    # ---------------------------------------------------------------- Menü
    def menu(self):
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        self.start_requested = False
        livedraw.set_redraw(lambda: self._draw_menu(self._widgets()))
        while not self.start_requested:
            widgets = self._widgets()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self._save()
                    return False
                if e.type == pygame.WINDOWSIZECHANGED:
                    self._layout()
                    continue
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.st.focus == "xcode":
                        self._import_code()      # Enter im Code-Feld = importieren
                    else:
                        self._start()
                    continue
                if e.type == pygame.MOUSEWHEEL and self.tab == "crosshair":
                    x0, cw = self._frame()
                    if self._profile_card(x0, cw, self.screen.get_height()).collidepoint(pygame.mouse.get_pos()):
                        self.profile_scroll = max(0, self.profile_scroll - e.y)
                    continue
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self.st.focus = None
                    continue
                if e.type == pygame.MOUSEWHEEL and self.tab == "result":
                    x0, cw = self._frame()
                    lst, _ = self._result_rects(x0, cw, self.screen.get_height())
                    if lst.collidepoint(pygame.mouse.get_pos()):
                        self.list_scroll = max(0, self.list_scroll - e.y)
                    else:
                        self.detail_scroll = max(0, min(self.detail_max, self.detail_scroll - e.y * 40))
                    continue
                if e.type == pygame.MOUSEWHEEL and self.tab == "help":
                    x0, cw = self._frame()
                    overflow = self._help_layout(x0, cw)[1] - (self.screen.get_height() - 16)
                    self.help_scroll = max(0, min(max(0, overflow), self.help_scroll - e.y * 40))
                    continue
                consumed = any(w.handle(e, self.st) for w in widgets)
                if e.type == pygame.MOUSEBUTTONDOWN and not consumed:
                    self.st.focus = None
                if e.type == pygame.MOUSEBUTTONUP:
                    self.st.drag = None
                if consumed:
                    widgets = self._widgets()   # Zustand hat sich geändert
            self._draw_menu(self._widgets())
            self.clock.tick(60)
        self._save()
        return True

    def _start(self):
        if self._valid():
            self.st.focus = None
            self.start_requested = True

    def _set_tab(self, tab):
        self.tab = tab
        self.st.focus = None
        if tab == "result":
            self._reload_history()

    def _widgets(self):
        w, h = self.screen.get_size()
        x0, cw = self._frame()
        out = [ui.Button((x0 + i * 180, 78, 170, 42), label, lambda k=key: self._set_tab(k), selected=self.tab == key)
               for i, (key, label) in enumerate(TABS)]
        return out + getattr(self, f"_widgets_{self.tab}")(x0, cw, h)

    def _start_button(self, x, y):
        return ui.Button((x, y, 360, 60), "START   (Enter)", self._start, selected=self._valid(), font="big")

    def _apply_button(self, rect):
        def apply():
            self.cfg["sens"] = f"{self.last_rec.recommended_sens:.3f}"
        return ui.Button(rect, f"Empfehlung übernehmen  ({self.last_rec.recommended_sens:.3f})", apply)

    def _widgets_training(self, x0, cw, h):
        out = [ui.TextField((x0 + 20, TOP + 84, 320, 44), "Valorant-Sensitivity", self.cfg, "sens"),
               ui.TextField((x0 + 20, TOP + 164, 320, 44), "Maus-DPI", self.cfg, "dpi"),
               ui.TextField((x0 + 20, TOP + 244, 320, 44), "Dauer in Sekunden", self.cfg, "duration")]
        for i, (key, (title, desc)) in enumerate(MODE_INFO.items()):
            out.append(ui.Button((x0 + 400, TOP + 62 + i * 96, cw - 420, 86), title,
                                 lambda k=key: self.cfg.update(mode=k), selected=self.cfg["mode"] == key, sub=desc))
        out.append(self._start_button(x0, h - 92))
        if self.last_rec:
            out.append(self._apply_button((x0 + 380, h - 92, 400, 60)))
        return out

    def _widgets_crosshair(self, x0, cw, h):
        xc = self.cfg["crosshair"]

        def getter(d, k):
            return lambda: d[k]

        def setter(d, k):
            return lambda v: d.__setitem__(k, v)

        def slider(x, y, label, d, k, lo, hi, step, fmt="{:.0f}"):
            return ui.Slider((x, y, 300, 30), label, getter(d, k), setter(d, k), lo, hi, step, f"{id(d)}{k}", fmt)

        def toggle(x, y, label, d, k):
            return ui.Toggle((x, y, 300, 30), label, getter(d, k), setter(d, k))

        a, b = x0 + 20, x0 + 350
        out = []
        for i, (_, col) in enumerate(crosshair.COLOR_PRESETS):
            out.append(ui.Button((a + (i % 4) * 76, TOP + 92 + (i // 4) * 46, 68, 38), "",
                                 lambda c=col: xc.update(color=list(c)), swatch=col,
                                 selected=tuple(xc["color"]) == col))
        y = TOP + 200
        out += [toggle(a, y, "Outline", xc, "outline"),
                slider(a, y + 34, "Deckkraft", xc, "outline_opacity", 0.0, 1.0, 0.05, "{:.2f}"),
                slider(a, y + 68, "Dicke", xc, "outline_thickness", 1, 6, 1),
                toggle(a, y + 112, "Center Dot", xc, "dot"),
                slider(a, y + 146, "Deckkraft", xc, "dot_opacity", 0.0, 1.0, 0.05, "{:.2f}"),
                slider(a, y + 180, "Dicke", xc, "dot_thickness", 1, 6, 1),
                toggle(a, y + 224, "Beim Schießen rot", xc, "fire_red")]
        for j, (key, title) in enumerate((("inner", "Innere Linien"), ("outer", "Äußere Linien"))):
            d, yy = xc[key], TOP + 92 + j * 200
            out += [toggle(b, yy, title, d, "show"),
                    slider(b, yy + 34, "Deckkraft", d, "opacity", 0.0, 1.0, 0.05, "{:.2f}"),
                    slider(b, yy + 68, "Länge", d, "length", 0, 20, 1),
                    slider(b, yy + 102, "Dicke", d, "thickness", 0, 10, 1),
                    slider(b, yy + 136, "Abstand", d, "offset", 0, 20 if key == "inner" else 40, 1)]
        out.append(ui.Button((x0, h - 92, 300, 60), "Zurücksetzen",
                             lambda: self.cfg.update(crosshair=crosshair.merged({}), crosshair_active=None)))
        out.append(ui.Button((x0 + 320, h - 92, 300, 60), "Fertig – zum Training", lambda: self._set_tab("training")))

        # --- Profile (Valorant-Profilcodes) ---
        pc, px, pw = self._profile_card(x0, cw, h), 0, 0
        px, pw = pc.x + 20, pc.w - 40
        out.append(ui.TextField((px, pc.y + 76, pw - 130, 42), "Valorant-Profilcode einfügen (Strg+V)", self.form,
                                "xcode", text=True, max_len=400, placeholder="z. B. 0;P;c;5;h;0;0l;4;0o;2;0a;1;1b;0"))
        out.append(ui.Button((px + pw - 120, pc.y + 76, 120, 42), "Importieren", self._import_code))
        half = (pw - 10) // 2
        out.append(ui.Button((px, pc.y + 128, half, 40), "Code kopieren", self._copy_code))
        out.append(ui.Button((px + half + 10, pc.y + 128, pw - half - 10, 40), "Als Profil speichern",
                             self._save_profile))
        profiles = self.cfg["crosshair_profiles"]
        order = list(range(len(profiles)))[::-1]          # neueste zuerst
        rows = self._profile_rows(pc)
        self.profile_scroll = max(0, min(self.profile_scroll, max(0, len(order) - rows)))
        for row, i in enumerate(order[self.profile_scroll:self.profile_scroll + rows]):
            y = pc.y + 214 + row * 46
            out.append(ui.Button((px, y, pw - 52, 40), profiles[i]["name"], lambda i=i: self._select_profile(i),
                                 selected=self.cfg.get("crosshair_active") == i, font="normal"))
            out.append(ui.Button((px + pw - 44, y, 44, 40), "×", lambda i=i: self._delete_profile(i), font="big"))
        return out

    # ------------------------------------------------------- Fadenkreuz-Profile
    def _profile_card(self, x0, cw, h):
        ch = h - TOP - 112
        return pygame.Rect(x0 + 690, TOP + PREVIEW_H + 16, cw - 690, ch - PREVIEW_H - 16)

    def _profile_rows(self, pc):
        return max(0, (pc.bottom - (pc.y + 214) - 6) // 46)

    def _status(self, text, ok=True):
        self.xstatus = (text, ui.GOOD if ok else ui.WARN)

    def _import_code(self):
        code = self.form["xcode"].strip()
        if not code:
            return self._status("Füge zuerst einen Code ein (Strg+V).", False)
        try:
            cfg = crosshair.parse_code(code, base=self.cfg["crosshair"])
        except ValueError as e:
            return self._status(f"Ungültiger Code: {e}", False)
        self.cfg["crosshair"] = cfg
        profiles = self.cfg["crosshair_profiles"]
        profiles.append({"name": f"Importiert {len(profiles) + 1}", "code": crosshair.to_code(cfg)})
        self.cfg["crosshair_active"] = len(profiles) - 1
        self.form["xcode"] = ""
        self.st.focus = None
        self.profile_scroll = 0
        self._status("Profil importiert und aktiviert.")

    def _copy_code(self):
        code = crosshair.to_code(self.cfg["crosshair"])
        try:
            pygame.scrap.put_text(code)
            self._status(f"Kopiert: {code}  – in Valorant beim Fadenkreuz-Profil importieren.")
        except pygame.error:
            self._status(f"Code: {code}", True)

    def _save_profile(self):
        profiles = self.cfg["crosshair_profiles"]
        profiles.append({"name": f"Eigenes Profil {len(profiles) + 1}",
                         "code": crosshair.to_code(self.cfg["crosshair"])})
        self.cfg["crosshair_active"] = len(profiles) - 1
        self.profile_scroll = 0
        self._status("Aktuelles Fadenkreuz als Profil gespeichert.")

    def _select_profile(self, i):
        p = self.cfg["crosshair_profiles"][i]
        try:
            self.cfg["crosshair"] = crosshair.parse_code(p["code"], base=self.cfg["crosshair"])
            self.cfg["crosshair_active"] = i
            self._status(f"„{p['name']}“ aktiviert")
        except ValueError as e:
            self._status(f"Profil defekt: {e}", False)

    def _delete_profile(self, i):
        profiles = self.cfg["crosshair_profiles"]
        name = profiles.pop(i)["name"]
        active = self.cfg.get("crosshair_active")
        if active == i:
            self.cfg["crosshair_active"] = None
        elif active is not None and active > i:
            self.cfg["crosshair_active"] = active - 1
        self._status(f"„{name}“ gelöscht")

    def _widgets_help(self, x0, cw, h):
        return [self._start_button(x0, h - 92)] if self._help_layout(x0, cw)[1] < h - 112 else []

    # ------------------------------------------------------- Ergebnisse
    def _reload_history(self):
        self.history = sessions.list_sessions(SESSIONS) if SESSIONS.exists() else []
        self._refresh_overall()
        paths = [s.path for s in self.history]
        if self.selected not in paths and self.selected != ALL:
            self.selected = ALL if paths else None
            self.detail_scroll = 0

    def _refresh_overall(self):
        """Gesamtbilanz hängt von der aktuell eingestellten Sens ab -> bei Änderung neu rechnen."""
        try:
            sens, dpi = float(self.cfg["sens"]), float(self.cfg["dpi"])
        except ValueError:
            sens, dpi = 0.35, 800.0
        self.overall = sessions.overall(self.history, sens, dpi) if self.history and sens > 0 and dpi > 0 else None

    def _selected_info(self):
        if self.selected == ALL:
            return self.overall
        return next((s for s in self.history or [] if s.path == self.selected), None)

    def _result_rects(self, x0, cw, h):
        ch = h - TOP - 112
        return pygame.Rect(x0, TOP, 420, ch), pygame.Rect(x0 + 440, TOP, cw - 440, ch)

    def _visible_rows(self, list_rect):
        return max(1, (list_rect.h - 70 - 100) // 82)   # 100 = fester Eintrag "Gesamtbilanz"

    def _select(self, path):
        self.selected = path
        self.detail_scroll = 0

    def _widgets_result(self, x0, cw, h):
        if self.history is None:
            self._reload_history()
        lst, _ = self._result_rects(x0, cw, h)
        out = []
        if self.overall:
            o = self.overall
            sub = (f"Alle {len(self.history)} Runden  →  Empfehlung {o.rec.recommended_sens:.3f}" if o.rec
                   else f"Alle {len(self.history)} Runden  ·  noch zu wenig Daten für eine Empfehlung")
            out.append(ui.Button((lst.x + 14, lst.y + 60, lst.w - 28, 74), "Gesamtbilanz",
                                 lambda: self._select(ALL), selected=self.selected == ALL, sub=sub))
        rows = self._visible_rows(lst)
        self.list_scroll = max(0, min(self.list_scroll, max(0, len(self.history) - rows)))
        for i, info in enumerate(self.history[self.list_scroll:self.list_scroll + rows]):
            out.append(ui.Button((lst.x + 14, lst.y + 160 + i * 82, lst.w - 28, 74), info.title,
                                 lambda p=info.path: self._select(p), selected=info.path == self.selected,
                                 sub=info.subtitle))
        info = self._selected_info()
        if info and info.rec:
            def apply(v=info.rec.recommended_sens):
                self.cfg["sens"] = f"{v:.3f}"
                self._refresh_overall()
            label = "Gesamt-Empfehlung übernehmen" if info is self.overall else "Diese Empfehlung übernehmen"
            out.append(ui.Button((x0, h - 92, 420, 60), f"{label}  ({info.rec.recommended_sens:.3f})", apply))
        out.append(ui.Button((x0 + cw - 240, h - 92, 240, 60), "Ordner öffnen", self._open_folder))
        return out

    def _open_folder(self):
        SESSIONS.mkdir(exist_ok=True)
        try:
            os.startfile(SESSIONS)   # Windows-Explorer
        except (AttributeError, OSError):
            pass

    # -------------------------------------------------------------- Zeichnen
    def _draw_menu(self, widgets):
        self._sync_layout()
        f, s = self.fonts, self.screen
        w, h = s.get_size()
        x0, cw = self._frame()
        s.fill(ui.BG)
        title = f.title.render("VALORANT AIM TRAINER", True, ui.ACCENT)
        s.blit(title, (x0, 20))
        s.blit(f.small.render(f"v{__version__}", True, ui.MUTED), (x0 + title.get_width() + 12, 36))
        badge = "● Raw Input aktiv" if self.raw_ok else "● Raw Input nicht verfügbar"
        img = f.small.render(badge, True, ui.GOOD if self.raw_ok else ui.WARN)
        s.blit(img, (x0 + cw - img.get_width(), 34))
        getattr(self, f"_draw_{self.tab}")(x0, cw, h)
        for wd in widgets:
            wd.draw(s, f, self.st)
        pygame.display.flip()

    def _draw_training(self, x0, cw, h):
        f, s = self.fonts, self.screen
        ch = h - TOP - 112
        left = ui.card(s, (x0, TOP, 360, ch), f, "Einstellungen")
        ui.card(s, (x0 + 380, TOP, cw - 380, ch), f, "Modus wählen")
        y = TOP + 312
        if self._valid():
            sens, dpi = float(self.cfg["sens"]), float(self.cfg["dpi"])
            for label, val in (("eDPI", f"{sens * dpi:.0f}"), ("cm pro 360°", f"{cm_per_360(sens, dpi):.2f}"),
                               ("Grad pro Mauscount", f"{0.07 * sens:.5f}")):
                s.blit(f.normal.render(label, True, ui.MUTED), (x0 + 20, y))
                img = f.bold.render(val, True, ui.TEXT)
                s.blit(img, (left.right - 20 - img.get_width(), y))
                y += 28
        else:
            s.blit(f.normal.render("Bitte gültige Zahlen eintragen", True, ui.WARN), (x0 + 20, y))
        ui.draw_wrapped(s, "Linke Maustaste = Schießen  ·  Kopf = Kill  ·  Esc = Pause (weiter oder beenden)",
                        f.small, ui.MUTED, x0 + 20, left.bottom - 52, 320, 2)

    def _draw_crosshair(self, x0, cw, h):
        f, s = self.fonts, self.screen
        ch = h - TOP - 112
        ui.card(s, (x0, TOP, 670, ch), f, "Fadenkreuz anpassen")
        s.blit(f.bold.render("Farbe", True, ui.MUTED), (x0 + 20, TOP + 62))
        s.blit(f.bold.render("Linien", True, ui.MUTED), (x0 + 350, TOP + 62))
        pc = ui.card(s, self._profile_card(x0, cw, h), f, "Fadenkreuz-Profile")
        if self.xstatus[0]:
            ui.draw_wrapped(s, self.xstatus[0], f.small, self.xstatus[1], pc.x + 20, pc.y + 174, pc.w - 40, 1)
        profiles = self.cfg["crosshair_profiles"]
        if not profiles:
            ui.draw_wrapped(s, "Noch keine Profile. Code aus Valorant einfügen (dort: Fadenkreuz → Profil "
                               "exportieren) oder aktuelles Fadenkreuz speichern.", f.small, ui.MUTED,
                            pc.x + 20, pc.y + 214, pc.w - 40, 2)
        elif len(profiles) > self._profile_rows(pc):
            img = f.small.render("Mausrad = mehr Profile", True, ui.MUTED)
            s.blit(img, (pc.right - 20 - img.get_width(), pc.y + 20))
        prev = ui.card(s, (x0 + 690, TOP, cw - 690, PREVIEW_H))
        inner = prev.inflate(-16, -16)
        if inner.w < 50 or inner.h < 50:
            return
        # Vorschau: echte Szene mit Bot in 5 m, gleiche Projektion wie im Training
        if self._preview is None or self._preview[0] != inner.size:
            self._preview = (inner.size, Renderer(pygame.Surface(inner.size)))
        rr = self._preview[1]
        rr.draw_world(Camera(1.0), [Bot((0.4, 1.6, 5.0))], env=self.env_static)
        hold = pygame.mouse.get_pressed()[0] and inner.collidepoint(pygame.mouse.get_pos())
        rr.draw_crosshair(self.cfg["crosshair"], firing=hold)
        rr.label("Vorschau – Maustaste gedrückt halten = Schussfarbe", (inner.w // 2, inner.h - 8),
                 anchor="midbottom", pad=(10, 3))
        s.blit(rr.screen, inner)

    def _help_layout(self, x0, cw):
        """Anleitungs-Kacheln auf zwei Spalten verteilen (jeweils in die kürzere)."""
        f = self.fonts
        col_w = (cw - 20) // 2
        top = TOP - self.help_scroll
        heights, cards = [top, top], []
        for title, text in HELP:
            c = 0 if heights[0] <= heights[1] else 1
            hh = 60 + ui.text_height(text, f.body, col_w - 40)
            cards.append((pygame.Rect(x0 + c * (col_w + 20), heights[c], col_w, hh), title, text))
            heights[c] += hh + 16
        return cards, max(heights) + self.help_scroll

    def _draw_help(self, x0, cw, h):
        f, s = self.fonts, self.screen
        bottom = h - 112 if self._help_layout(x0, cw)[1] < h - 112 else h - 16
        s.set_clip(pygame.Rect(0, TOP - 4, s.get_width(), bottom - TOP + 4))
        for rect, title, text in self._help_layout(x0, cw)[0]:
            ui.card(s, rect)
            s.blit(f.big.render(title, True, ui.ACCENT), (rect.x + 20, rect.y + 14))
            ui.draw_wrapped(s, text, f.body, ui.TEXT, rect.x + 20, rect.y + 52, rect.w - 40)
        s.set_clip(None)
        if self._help_layout(x0, cw)[1] > bottom:
            img = f.small.render("▼  Mausrad zum Scrollen", True, ui.MUTED)
            s.blit(img, (x0 + cw - img.get_width(), 34 + 22))

    def _draw_result(self, x0, cw, h):
        f, s = self.fonts, self.screen
        lst, det = self._result_rects(x0, cw, h)
        ui.card(s, lst, f, f"Gespeicherte Runden ({len(self.history)})")
        ui.card(s, det)
        if not self.history:
            ui.draw_wrapped(s, "Noch keine Runde gespielt. Starte im Tab „Training“ eine Runde – danach "
                               "erscheint sie hier.", f.normal, ui.MUTED, lst.x + 20, lst.y + 60, lst.w - 40)
            return
        s.blit(f.small.render("Einzelne Runden (neueste oben)", True, ui.MUTED), (lst.x + 20, lst.y + 138))
        rows = self._visible_rows(lst)
        if len(self.history) > rows:
            hint = f"{self.list_scroll + 1}–{min(len(self.history), self.list_scroll + rows)} von " \
                   f"{len(self.history)}  ·  Mausrad zum Blättern"
            s.blit(f.small.render(hint, True, ui.MUTED), (lst.x + 20, lst.bottom - 26))
        info = self._selected_info()
        if info:
            self._draw_report(info, det.inflate(-8, -8))

    def _draw_sens_chart(self, info, rect):
        """Verlauf: ideale Sens je Runde (Punkte) gegen eingestellte Sens und Zielwert (Linien)."""
        f, s = self.fonts, self.screen
        s.blit(f.bold.render("Ideale Sens je Runde", True, ui.TEXT), (rect.x, rect.y))
        plot = pygame.Rect(rect.x + 52, rect.y + 30, rect.w - 175, rect.h - 52)
        pygame.draw.rect(s, (20, 22, 30), plot, border_radius=6)
        vals = [p for _, p, _ in info.series] + [info.current] + ([info.target] if info.target else [])
        lo, hi = min(vals), max(vals)
        pad = max((hi - lo) * 0.15, 0.01)
        lo, hi = lo - pad, hi + pad

        def ypos(v):
            return plot.bottom - (v - lo) / (hi - lo) * plot.h

        for v in (lo + pad, hi - pad):
            img = f.small.render(f"{v:.3f}", True, ui.MUTED)
            s.blit(img, (plot.x - 8 - img.get_width(), ypos(v) - 9))
        lines = [(info.current, ui.MUTED, "eingestellt")]
        if info.target:
            lines.append((info.target, ui.GOOD, "Zielwert"))
        label_ys = []
        for v, col, name in lines:
            yy = ypos(v)
            for xx in range(plot.x, plot.right, 12):    # gestrichelt
                pygame.draw.line(s, col, (xx, yy), (min(xx + 6, plot.right), yy), 2)
            ly = yy - 9
            for other in label_ys:                       # Beschriftungen nicht übereinander
                if abs(ly - other) < 18:
                    ly = other + 18 if ly >= other else other - 18
            label_ys.append(ly)
            s.blit(f.small.render(f"{name} {v:.3f}", True, col), (plot.right + 8, ly))
        n = len(info.series)
        pts = [(plot.x + 14 + i * (plot.w - 28) / (n - 1), ypos(p)) for i, (_, p, _) in enumerate(info.series)]
        pygame.draw.lines(s, ui.HIGHLIGHT, False, pts, 2)
        for pt in pts:
            pygame.draw.circle(s, ui.HIGHLIGHT, pt, 5)
        first, last = info.series[0][0], info.series[-1][0]
        s.blit(f.small.render(f"{first:%d.%m. %H:%M}", True, ui.MUTED), (plot.x, plot.bottom + 4))
        img = f.small.render(f"{last:%d.%m. %H:%M}", True, ui.MUTED)
        s.blit(img, (plot.right - img.get_width(), plot.bottom + 4))
        return rect.bottom + 4

    def _draw_report(self, info, area):
        """Auswertung einer Runde in einer scrollbaren Spalte."""
        f, s = self.fonts, self.screen
        head, best, sections = report_sections(info.report)
        width = area.w - 40
        s.set_clip(area)
        y = area.y + 14 - self.detail_scroll
        s.blit(f.big.render(info.title, True, ui.TEXT), (area.x + 20, y))
        y += 38
        s.blit(f.small.render(info.info_line, True, ui.MUTED), (area.x + 20, y))
        y += 26
        for line in head:
            y = ui.draw_wrapped(s, line, f.body, ui.MUTED, area.x + 20, y, width, 3)
        if best:
            banner = pygame.Rect(area.x + 12, y + 10, area.w - 24, 56)
            pygame.draw.rect(s, (60, 48, 24), banner, border_radius=8)
            pygame.draw.rect(s, ui.HIGHLIGHT, banner, 2, border_radius=8)
            s.blit(f.big.render(best.split("   ")[0], True, ui.HIGHLIGHT), (banner.x + 16, banner.y + 6))
            s.blit(f.small.render(best.split("   ", 1)[-1].strip("()"), True, ui.HIGHLIGHT),
                   (banner.x + 16, banner.y + 34))
            y = banner.bottom + 6
        if getattr(info, "series", None) and len(info.series) >= 2:
            y = self._draw_sens_chart(info, pygame.Rect(area.x + 20, y + 16, width, 170))
        for title, lines in sections:
            y += 14
            pygame.draw.line(s, ui.HOVER, (area.x + 20, y), (area.right - 20, y))
            y += 10
            s.blit(f.bold.render(title, True, ui.ACCENT), (area.x + 20, y))
            y += 30
            for ln in lines:
                color = ui.GOOD if ln.startswith("  ->") else (ui.HIGHLIGHT if ln.startswith("*") else ui.TEXT)
                text = ln.replace("  -> ", "→  ").replace("* ", "•  ", 1)
                y = ui.draw_wrapped(s, text, f.body, color, area.x + 20, y, width, 3)
        s.set_clip(None)
        self.detail_max = max(0, y + self.detail_scroll - area.bottom + 20)
        if self.detail_max:
            img = f.small.render("▼ Mausrad zum Scrollen", True, ui.MUTED)
            s.blit(img, (area.right - img.get_width() - 14, area.bottom - 24))

    # -------------------------------------------------------------- Training
    def train(self):
        sens, dpi = float(self.cfg["sens"]), float(self.cfg["dpi"])
        xc = self.cfg["crosshair"]
        cam = Camera(sens)
        mode = MODES[self.cfg["mode"]](cam)
        env = Environment(BOUNDS, seed=int(time.time())) if hasattr(mode, "move") else self.env_static
        title = MODE_INFO[mode.name][0]
        duration = float(self.cfg["duration"])
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.set_relative_mode(True)
        self.raw.drain()
        last = time.perf_counter()
        played = 0.0          # gespielte Zeit ohne Pausen
        paused = False
        held = False          # linke Maustaste gedrückt
        fire_until = 0.0
        running = True

        def pause():
            """Esc / Alt-Tab / minimiert: Zeit anhalten, Maus freigeben, Pausenmenü zeigen."""
            nonlocal paused, held
            paused, held = True, False
            pygame.mouse.set_relative_mode(False)
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)

        def resume():
            nonlocal paused
            paused = False
            pygame.mouse.set_visible(False)
            pygame.event.set_grab(True)
            pygame.mouse.set_relative_mode(True)
            self.raw.drain()  # Klick auf "Weiterspielen" ist kein Schuss

        def stop():
            nonlocal running
            running = False

        def draw_frame():
            """Ein Bild zeichnen - auch aus livedraw heraus, während das Fenster gezogen wird."""
            self._sync_layout()
            r, now_ = self.r, last
            remaining_ = max(0.0, duration - played)
            self.screen.fill((0, 0, 0))
            r.draw_world(cam, [t for t in mode.targets if t.alive], mode.dead, now_,
                         getattr(mode, "covers", ()), env)
            r.draw_crosshair(xc, firing=held or now_ < fire_until)
            r.label(f"{title}   ·   {remaining_:4.1f} s", (14, 14), big=True)
            r.label(f"Kills {mode.kills}    Schüsse {mode.shots}    Körper {mode.body_hits}", (r.w - 14, 14),
                    anchor="topright")
            r.label(f"{self.clock.get_fps():.0f} FPS", (r.w - 14, r.h - 14), anchor="bottomright",
                    color=(170, 175, 190))
            if hasattr(mode, "move"):
                moving = mode.speed > 1.35
                r.label("In Bewegung – Schüsse streuen" if moving else "Stehend – volle Genauigkeit",
                        (14, r.h - 14), anchor="bottomleft", color=(255, 140, 110) if moving else (140, 255, 160))
            if played < 4 and not paused:
                hint = "Linke Maustaste = Schießen   ·   Ziel auf den gelben Kopf   ·   Esc = Pause"
                if hasattr(mode, "move"):
                    hint = "W A S D = Laufen   ·   " + hint
                r.label(hint, (r.w // 2, 70), anchor="midtop", color=(255, 225, 140))
            if paused:
                self._draw_pause(self._pause_buttons(resume, stop), remaining_)
            pygame.display.flip()

        livedraw.set_redraw(draw_frame)
        while running:
            now = time.perf_counter()
            pause_buttons = self._pause_buttons(resume, stop) if paused else []
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    resume() if paused else pause()
                elif e.type == pygame.WINDOWSIZECHANGED:
                    self._layout()
                elif e.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
                    if not paused:
                        pause()
                elif paused:
                    for b in pause_buttons:
                        if b.handle(e, self.st):
                            break
                elif not self.raw_ok and e.type == pygame.MOUSEMOTION:
                    cam.apply_counts(*e.rel)
                    mode.on_input(now)
                elif not self.raw_ok and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    mode.on_click(now)
                    fire_until = now + FIRE_FLASH
            # Raw-Events in Originalreihenfolge: Klick wird mit der Blickrichtung
            # zu genau diesem Zeitpunkt ausgewertet.
            for ev in self.raw.drain():
                if paused or not pygame.key.get_focused():
                    continue
                if ev.dx or ev.dy:
                    cam.apply_counts(ev.dx, ev.dy)
                    mode.on_input(ev.t)
                if ev.left_down:
                    mode.on_click(ev.t)
                    held, fire_until = True, ev.t + FIRE_FLASH
                if ev.left_up:
                    held = False
            if not paused:
                dt = min(now - last, 0.05)   # nach Pause kein Teleport des Ziels
                if hasattr(mode, "move"):
                    k = pygame.key.get_pressed()
                    mode.move(k[pygame.K_w] - k[pygame.K_s], k[pygame.K_d] - k[pygame.K_a], dt)
                mode.update(now, dt)
                played += dt
            last = now
            remaining = duration - played
            if remaining <= 0:
                running = False

            draw_frame()
            self.clock.tick(1000 if not paused else 30)

        livedraw.set_redraw(None)
        pygame.mouse.set_relative_mode(False)
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        self._finish(mode, sens, dpi, duration)

    def _pause_rect(self):
        w, h = self.screen.get_size()
        return pygame.Rect((w - 460) // 2, (h - 300) // 2, 460, 300)

    def _pause_buttons(self, resume, stop):
        box = self._pause_rect()
        return [ui.Button((box.x + 30, box.y + 120, box.w - 60, 58), "Weiterspielen", resume, selected=True,
                          font="big"),
                ui.Button((box.x + 30, box.y + 192, box.w - 60, 58), "Beenden und Auswertung ansehen", stop)]

    def _draw_pause(self, buttons, remaining):
        f, s = self.fonts, self.screen
        shade = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        shade.fill((8, 10, 14, 170))
        s.blit(shade, (0, 0))
        box = ui.card(s, self._pause_rect(), border=ui.HOVER)
        img = f.title.render("Pause", True, ui.TEXT)
        s.blit(img, img.get_rect(midtop=(box.centerx, box.y + 20)))
        img = f.normal.render(f"Die Zeit ist angehalten  ·  noch {remaining:.0f} s", True, ui.MUTED)
        s.blit(img, img.get_rect(midtop=(box.centerx, box.y + 72)))
        for b in buttons:
            b.draw(s, f, self.st)
        img = f.small.render("Esc = weiterspielen", True, ui.MUTED)
        s.blit(img, img.get_rect(midbottom=(box.centerx, box.bottom - 12)))

    def _finish(self, mode, sens, dpi, duration):
        session = {"started": datetime.now().isoformat(timespec="seconds"),
                   "settings": {"sens": sens, "dpi": dpi, "mode": mode.name, "duration": duration,
                                "raw_input": self.raw_ok},
                   "trials": mode.trials, "tracking": mode.tracking,
                   "peeks": getattr(mode, "peeks", []), "shots": mode.shots, "kills": mode.kills,
                   "body_hits": mode.body_hits, "moving_shots": getattr(mode, "moving_shots", 0)}
        flicks, tracking, rec = analyze_session(session)
        self.report = build_report(session, flicks, tracking, rec)
        self.report.insert(2, f"Körpertreffer (kein Kill): {mode.body_hits}")
        self.last_rec = rec if mode.name != "peek" else None
        self.tab = "result"
        SESSIONS.mkdir(exist_ok=True)
        stem = SESSIONS / f"{datetime.now():%Y%m%d_%H%M%S}_{mode.name}"
        stem.with_suffix(".json").write_text(json.dumps(session), "utf-8")
        stem.with_suffix(".txt").write_text("\n".join(self.report), "utf-8")
        self._reload_history()
        self._select(stem.with_suffix(".json"))
        self.list_scroll = 0

    # ------------------------------------------------------- Tipps vor dem Start
    def _brief_rect(self):
        w, h = self.screen.get_size()
        bw, bh = min(760, w - 40), min(560, h - 40)
        return pygame.Rect((w - bw) // 2, (h - bh) // 2, bw, bh)

    def _brief_buttons(self, go, back):
        box = self._brief_rect()
        return [ui.Button((box.x + 30, box.bottom - 86, box.w - 260, 60), "Los geht's   (Enter)", go,
                          selected=True, font="big"),
                ui.Button((box.right - 210, box.bottom - 86, 180, 60), "Zurück   (Esc)", back)]

    def briefing(self):
        """Tipps zum gewählten Modus vor jeder Runde. True = starten, False = zurück ins Menü."""
        mode = self.cfg["mode"]
        cam = Camera(1.0)
        bot = Bot((0.6, 1.6, 9.0))
        choice = [None]

        def go():
            choice[0] = True

        def back():
            choice[0] = False

        livedraw.set_redraw(lambda: self._draw_briefing(mode, cam, bot, self._brief_buttons(go, back)))
        while choice[0] is None:
            buttons = self._brief_buttons(go, back)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.WINDOWSIZECHANGED:
                    self._layout()
                elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    go()
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    back()
                else:
                    for b in buttons:
                        if b.handle(e, self.st):
                            break
            self._draw_briefing(mode, cam, bot, self._brief_buttons(go, back))
            self.clock.tick(60)
        return choice[0]

    def _draw_briefing(self, mode, cam, bot, buttons):
        self._sync_layout()
        f, s = self.fonts, self.screen
        s.fill((0, 0, 0))
        self.r.draw_world(cam, [bot], env=self.env_static)
        shade = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        shade.fill((8, 10, 14, 175))
        s.blit(shade, (0, 0))
        box = ui.card(s, self._brief_rect(), border=ui.HOVER)
        x, w = box.x + 30, box.w - 60
        s.blit(f.small.render("GLEICH GEHT'S LOS", True, ui.MUTED), (x, box.y + 22))
        s.blit(f.title.render(MODE_INFO[mode][0], True, ui.ACCENT), (x, box.y + 40))
        y = ui.draw_wrapped(s, MODE_INFO[mode][1], f.body, ui.MUTED, x, box.y + 88, w, 3) + 12
        s.blit(f.bold.render("Tipps für diesen Modus", True, ui.TEXT), (x, y))
        y += 30
        for tip in MODE_TIPS[mode]:
            y = ui.draw_wrapped(s, f"•  {tip}", f.body, ui.TEXT, x, y, w, 3) + 4
        y += 10
        s.blit(f.bold.render("Allgemein", True, ui.TEXT), (x, y))
        y += 30
        for tip in GENERAL_TIPS:
            y = ui.draw_wrapped(s, f"•  {tip}", f.body, ui.MUTED, x, y, w, 3) + 4
        keys = "Linke Maustaste = Schießen  ·  Ziel auf den gelben Kopf"
        if mode == "peek":
            keys = "W A S D = Laufen  ·  " + keys
        s.blit(f.small.render(keys, True, ui.HIGHLIGHT), (x, box.bottom - 116))
        for b in buttons:
            b.draw(s, f, self.st)
        pygame.display.flip()

    # ------------------------------------------------------- Pflicht-Update
    def update_gate(self):
        """Vor dem Menü: neue Version auf GitHub? Dann muss aktualisiert werden.
        True = weiter ins Programm, False = Programm beenden (Update läuft / Nutzer beendet)."""
        if not (FROZEN or os.environ.get("AIM_UPDATE_TEST")):
            return True   # Entwicklungsversion aktualisiert sich nicht selbst
        state = {"phase": "check", "info": None, "done": 0, "total": 0, "error": "", "path": None}

        def worker_check():
            state["info"] = updater.check()
            state["phase"] = "ask" if state["info"] else "none"

        def worker_download():
            try:
                state["path"] = updater.download(state["info"], lambda d, t: state.update(done=d, total=t))
                state["phase"] = "install"
            except OSError as e:
                state["error"], state["phase"] = str(e) or "Download fehlgeschlagen.", "ask"

        import threading
        threading.Thread(target=worker_check, daemon=True).start()
        choice = [None]

        def start_download():
            state["phase"], state["error"] = "download", ""
            threading.Thread(target=worker_download, daemon=True).start()

        def quit_app():
            choice[0] = False

        livedraw.set_redraw(lambda: self._draw_update(state, self._update_buttons(state, start_download, quit_app)))
        while choice[0] is None:
            if state["phase"] == "none":
                return True
            if state["phase"] == "install":
                updater.run_installer(state["path"])
                return False
            buttons = self._update_buttons(state, start_download, quit_app)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.WINDOWSIZECHANGED:
                    self._layout()
                for b in buttons:
                    if b.handle(e, self.st):
                        break
            self._draw_update(state, self._update_buttons(state, start_download, quit_app))
            self.clock.tick(60)
        return choice[0]

    def _update_rect(self):
        w, h = self.screen.get_size()
        bw, bh = min(620, w - 40), min(400, h - 40)
        return pygame.Rect((w - bw) // 2, (h - bh) // 2, bw, bh)

    def _update_buttons(self, state, start_download, quit_app):
        if state["phase"] != "ask":
            return []
        box = self._update_rect()
        return [ui.Button((box.x + 30, box.bottom - 86, box.w - 230, 60), "Jetzt aktualisieren", start_download,
                          selected=True, font="big"),
                ui.Button((box.right - 180, box.bottom - 86, 150, 60), "Beenden", quit_app)]

    def _draw_update(self, state, buttons):
        self._sync_layout()
        f, s = self.fonts, self.screen
        s.fill(ui.BG)
        box = ui.card(s, self._update_rect(), border=ui.HOVER)
        x, w = box.x + 30, box.w - 60
        info = state["info"]
        if state["phase"] == "check":
            s.blit(f.big.render("Suche nach Updates …", True, ui.TEXT), (x, box.y + 30))
            ui.draw_wrapped(s, f"Installierte Version: {__version__}", f.body, ui.MUTED, x, box.y + 76, w)
        else:
            s.blit(f.title.render("Update verfügbar", True, ui.ACCENT), (x, box.y + 24))
            y = ui.draw_wrapped(s, f"Version {info.version} ist da – du hast Version {__version__}. Damit alle "
                                   f"mit derselben Version trainieren, muss das Update installiert werden. "
                                   f"Deine Einstellungen und Runden bleiben erhalten.",
                                f.body, ui.TEXT, x, box.y + 78, w, 3)
            if info.notes:
                notes = "Neu: " + " · ".join(ln.strip("-*• ").strip() for ln in info.notes.splitlines() if ln.strip())
                y = ui.draw_wrapped(s, notes[:300], f.small, ui.MUTED, x, y + 10, w, 2)
            if state["phase"] == "download":
                bar = pygame.Rect(x, box.bottom - 80, w, 22)
                pygame.draw.rect(s, ui.FIELD, bar, border_radius=6)
                k = state["done"] / state["total"] if state["total"] else 0
                pygame.draw.rect(s, ui.ACCENT, (bar.x, bar.y, int(bar.w * k), bar.h), border_radius=6)
                s.blit(f.small.render(f"Lade herunter … {state['done'] / 1e6:.1f} / {state['total'] / 1e6:.1f} MB",
                                      True, ui.MUTED), (x, bar.bottom + 8))
            if state["error"]:
                s.blit(f.small.render(state["error"], True, ui.WARN), (x, box.bottom - 112))
        for b in buttons:
            b.draw(s, f, self.st)
        pygame.display.flip()

    def run(self):
        try:
            if not self.update_gate():
                return
            while self.menu():
                if self.briefing():
                    self.train()
        finally:
            self.raw.stop()
            pygame.quit()


def main():
    App(fullscreen="--fullscreen" in sys.argv).run()
