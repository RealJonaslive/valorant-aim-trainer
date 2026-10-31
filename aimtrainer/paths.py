"""Wo liegt was - als Python-Projekt (Entwicklung) und als installierte .exe.

- Entwicklung:  alles im Projektordner (config.json, sessions/, assets/).
- Installiert:  Programmdateien im Installationsordner (werden bei Updates ersetzt),
                Einstellungen und Runden in %APPDATA%\\ValorantAimTrainer - bleiben bei
                Updates und Neuinstallation erhalten.
"""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))          # gebündelte Dateien (assets/)
DATA_DIR = (Path(os.environ.get("APPDATA", Path.home())) / "ValorantAimTrainer") if FROZEN else APP_DIR

CONFIG = DATA_DIR / "config.json"
SESSIONS = DATA_DIR / "sessions"
ICON = RES_DIR / "assets" / "icon.png"
ERROR_LOG = DATA_DIR / "fehler.log"
