"""Bild auch WAEHREND Fenster-Ziehen / Groesse-Aendern neu zeichnen.

Problem: Zieht man unter Windows ein Fenster (Titelleiste oder Rand), laeuft eine
Windows-interne Schleife, und unser pygame-Loop steht still, bis die Maus
losgelassen wird. Das Bild (z. B. das Pausenmenue) friert ein bzw. wird verzerrt
und springt erst danach an die richtige Stelle.

Loesung: SDL meldet Fenster-Ereignisse (verschoben, Groesse geaendert, neu
sichtbar) auch waehrend dieser Schleife an registrierte "Event Watches". Wir
haengen uns ueber ctypes an dieselbe SDL2.dll, die pygame benutzt, und rufen
dort die gerade aktive Zeichenfunktion auf. So bleibt jeder Bildschirm - auch
das Pausenmenue - immer korrekt im Fenster mittig.
"""
import ctypes
import os
import sys

import pygame

SDL_WINDOWEVENT = 0x200
REDRAW_EVENTS = {3, 4, 5, 6}   # EXPOSED, MOVED, RESIZED, SIZE_CHANGED


class _WindowEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("timestamp", ctypes.c_uint32),
                ("windowID", ctypes.c_uint32), ("event", ctypes.c_uint8)]


_state = {"cb": None, "redraw": None, "busy": False, "calls": 0}


def install() -> bool:
    """Einmalig nach pygame.display.set_mode() aufrufen."""
    if _state["cb"] is not None:
        return True
    if sys.platform != "win32":
        return False
    # Entwicklung: neben pygame; gepackte .exe (PyInstaller): je nach Version dort oder im Bundle-Ordner
    folders = [os.path.dirname(pygame.__file__), getattr(sys, "_MEIPASS", ""),
               os.path.join(getattr(sys, "_MEIPASS", ""), "pygame")]
    path = next((os.path.join(d, "SDL2.dll") for d in folders if d and os.path.exists(os.path.join(d, "SDL2.dll"))),
                None)
    if not path:
        return False
    sdl = ctypes.CDLL(path)
    FILTER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

    def watch(_userdata, event_ptr):
        ev = ctypes.cast(event_ptr, ctypes.POINTER(_WindowEvent)).contents
        fn = _state["redraw"]
        if ev.type == SDL_WINDOWEVENT and ev.event in REDRAW_EVENTS and fn and not _state["busy"]:
            _state["busy"] = True
            try:
                fn()
                _state["calls"] += 1
            except Exception:   # nie aus dem SDL-Callback heraus crashen
                pass
            finally:
                _state["busy"] = False
        return 1

    _state["cb"] = FILTER(watch)          # Referenz halten, sonst GC-Crash
    sdl.SDL_AddEventWatch.argtypes = [FILTER, ctypes.c_void_p]
    sdl.SDL_AddEventWatch(_state["cb"], None)
    return True


def set_redraw(fn) -> None:
    """Zeichenfunktion des aktuellen Bildschirms (Menü, Tipps, Training/Pause)."""
    _state["redraw"] = fn
