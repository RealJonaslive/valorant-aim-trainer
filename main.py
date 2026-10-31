"""Start: python main.py              (Fenster: verschieben, minimieren, maximieren, Groesse ziehen)
       python main.py --fullscreen (exklusives Vollbild)

Ohne Konsolenfenster (Desktop-Verknuepfung / installierte .exe) sieht man Fehler nicht -
deshalb landen sie in fehler.log (Entwicklung: Projektordner, installiert: %APPDATA%\\ValorantAimTrainer).
"""
import os
import sys
import traceback

if __name__ == "__main__":
    from aimtrainer.paths import APP_DIR, DATA_DIR, ERROR_LOG

    os.chdir(APP_DIR)   # Verknuepfung kann aus einem beliebigen Ordner starten
    try:
        from aimtrainer.app import main
        main()
    except Exception:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text(traceback.format_exc(), "utf-8")
        if sys.stderr:
            traceback.print_exc()
        raise SystemExit(1)
