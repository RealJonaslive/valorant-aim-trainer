"""Konfigurierbares Fadenkreuz (Farbe, Outline, Center-Dot, innere/aeussere Linien).

Alle Werte in Pixeln bzw. Deckkraft 0..1 - gleiche Logik wie die Fadenkreuz-
Einstellungen in Valorant. Beim Schiessen wechselt die Farbe kurz auf die
Schussfarbe (Standard: Rot).
"""
import copy

import pygame

COLOR_PRESETS = [
    ("Weiß", (255, 255, 255)), ("Grün", (0, 255, 0)), ("Gelbgrün", (127, 255, 0)),
    ("Grüngelb", (223, 255, 0)), ("Gelb", (255, 255, 0)), ("Cyan", (0, 255, 255)),
    ("Pink", (255, 0, 255)), ("Rot", (255, 0, 0)),
]

DEFAULT = {
    "color": [0, 255, 0],
    "outline": True, "outline_opacity": 0.5, "outline_thickness": 1,
    "dot": False, "dot_opacity": 1.0, "dot_thickness": 2,
    "inner": {"show": True, "opacity": 0.8, "length": 6, "thickness": 2, "offset": 3,
              "split": False, "vlength": 6},
    "outer": {"show": False, "opacity": 0.35, "length": 2, "thickness": 2, "offset": 10,
              "split": False, "vlength": 2},
    "fire_red": True, "fire_color": [255, 30, 30],
}


def merged(cfg):
    """Gespeicherte Einstellungen mit Defaults auffuellen (neue Optionen, alte config.json)."""
    out = copy.deepcopy(DEFAULT)
    for k, v in (cfg or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Valorant-Fadenkreuz-Codes ("Profilcode importieren/exportieren")
#
# Aufbau: "0;P;c;5;h;0;0l;4;0o;2;0a;1;1b;0"
#   "0"        Formatversion
#   "P"/"A"/"S" Abschnitt: Primaer / Zielen (ADS) / Sniper - wir nutzen "P"
#   danach Schluessel;Wert-Paare. Fehlende Schluessel = Valorant-Standardwert.
# Unbekannte Schluessel (Bewegungs-/Schussfehler, Fade, ...) werden ignoriert.
# ---------------------------------------------------------------------------
VALORANT_DEFAULT = {
    "color": [255, 255, 255],
    "outline": True, "outline_opacity": 0.5, "outline_thickness": 1,
    "dot": False, "dot_opacity": 1.0, "dot_thickness": 2,
    "inner": {"show": True, "opacity": 0.8, "length": 6, "thickness": 2, "offset": 3,
              "split": False, "vlength": 6},
    "outer": {"show": True, "opacity": 0.35, "length": 2, "thickness": 2, "offset": 10,
              "split": False, "vlength": 2},
}

# Code-Schluessel -> (Pfad in unserer Einstellung, Typ, min, max)
_KEYS = {
    "h": (("outline",), bool, 0, 1), "t": (("outline_thickness",), int, 1, 6),
    "o": (("outline_opacity",), float, 0, 1),
    "d": (("dot",), bool, 0, 1), "z": (("dot_thickness",), int, 1, 6), "a": (("dot_opacity",), float, 0, 1),
    "0b": (("inner", "show"), bool, 0, 1), "0t": (("inner", "thickness"), int, 0, 10),
    "0l": (("inner", "length"), int, 0, 20), "0o": (("inner", "offset"), int, 0, 20),
    "0a": (("inner", "opacity"), float, 0, 1),
    "0g": (("inner", "split"), bool, 0, 1), "0v": (("inner", "vlength"), int, 0, 20),
    "1b": (("outer", "show"), bool, 0, 1), "1t": (("outer", "thickness"), int, 0, 10),
    "1l": (("outer", "length"), int, 0, 20), "1o": (("outer", "offset"), int, 0, 40),
    "1a": (("outer", "opacity"), float, 0, 1),
    "1g": (("outer", "split"), bool, 0, 1), "1v": (("outer", "vlength"), int, 0, 20),
}


def _get(cfg, path):
    for p in path:
        cfg = cfg[p]
    return cfg


def _set(cfg, path, value):
    for p in path[:-1]:
        cfg = cfg[p]
    cfg[path[-1]] = value


def parse_code(code, base=None):
    """Valorant-Profilcode -> Fadenkreuz-Einstellungen. Wirft ValueError bei ungueltigem Code.
    'base' liefert die Werte, die es in Valorant nicht gibt (z. B. 'Beim Schiessen rot')."""
    tokens = [t.strip() for t in code.strip().strip(";").split(";")]
    if not tokens or tokens[0] != "0":
        raise ValueError("Ein Valorant-Fadenkreuz-Code beginnt mit 0; …")
    cfg = merged(base)
    for k, v in copy.deepcopy(VALORANT_DEFAULT).items():
        cfg[k] = v
    section, color_idx, custom, i = None, 0, None, 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("P", "A", "S"):
            section, i = tok, i + 1
            continue
        if i + 1 >= len(tokens):
            raise ValueError(f"Wert für „{tok}“ fehlt.")
        val, i = tokens[i + 1], i + 2
        if section != "P":
            continue
        try:
            if tok == "c":
                color_idx = int(val)
            elif tok == "u":
                custom = val
            elif tok in _KEYS:
                path, typ, lo, hi = _KEYS[tok]
                num = max(lo, min(hi, float(val)))
                _set(cfg, path, bool(num) if typ is bool else typ(round(num) if typ is int else num))
        except ValueError:
            raise ValueError(f"Ungültiger Wert „{val}“ bei „{tok}“.") from None
    if color_idx == 8 and custom:
        h = custom.lstrip("#")
        if len(h) not in (6, 8):
            raise ValueError("Eigene Farbe muss ein Hex-Code sein (z. B. FF0000FF).")
        cfg["color"] = [int(h[j:j + 2], 16) for j in (0, 2, 4)]
    elif 0 <= color_idx < len(COLOR_PRESETS):
        cfg["color"] = list(COLOR_PRESETS[color_idx][1])
    return cfg


def to_code(cfg):
    """Fadenkreuz-Einstellungen -> Valorant-Profilcode (nur Abweichungen vom Standard,
    genau wie Valorant selbst exportiert)."""
    parts = []
    rgb = tuple(cfg["color"])
    presets = [c for _, c in COLOR_PRESETS]
    if rgb in presets:
        if presets.index(rgb) != 0:
            parts += ["c", str(presets.index(rgb))]
    else:
        parts += ["c", "8", "u", "%02X%02X%02XFF" % rgb]
    for key, (path, typ, _, _) in _KEYS.items():
        val, default = _get(cfg, path), _get(VALORANT_DEFAULT, path)
        if typ is float:
            if abs(float(val) - default) > 1e-6:
                parts += [key, f"{float(val):.3f}".rstrip("0").rstrip(".")]
        elif typ is bool:
            if bool(val) != default:
                parts += [key, str(int(bool(val)))]
        elif int(val) != default:
            parts += [key, str(int(val))]
    return "0;P;" + ";".join(parts) if parts else "0"


def draw(surface, center, cfg, firing=False):
    color = cfg["fire_color"] if firing and cfg["fire_red"] else cfg["color"]
    rects = []   # (Rect relativ zur Mitte, Deckkraft)
    if cfg["dot"]:
        s = int(cfg["dot_thickness"])
        if s > 0:
            rects.append((pygame.Rect(-(s // 2), -(s // 2), s, s), cfg["dot_opacity"]))
    for key in ("inner", "outer"):
        ln = cfg[key]
        if not ln["show"] or ln["opacity"] <= 0 or ln["thickness"] <= 0:
            continue
        T, O = int(ln["thickness"]), int(ln["offset"])
        L = int(ln["length"])
        Lv = int(ln.get("vlength", L)) if ln.get("split") else L
        # Pixelgenaue Geometrie um den Mittelpunkt (0,0 = Pixel unten rechts der Bildmitte):
        # ungerade Dicke -> Linie liegt mittig auf dem Mittelpunkt-Pixel, das selbst frei bleibt
        # (bzw. vom Center Dot gefuellt wird); gerade Dicke -> Mitte liegt auf der Pixelkante.
        half, a = T % 2, -(T // 2)
        op = ln["opacity"]
        if L > 0:
            rects += [(pygame.Rect(half + O, a, L, T), op), (pygame.Rect(-O - L, a, L, T), op)]
        if Lv > 0:
            rects += [(pygame.Rect(a, half + O, T, Lv), op), (pygame.Rect(a, -O - Lv, T, Lv), op)]
    if not rects:
        return
    ot = int(cfg["outline_thickness"]) if cfg["outline"] else 0
    size = 2 * (max(max(abs(r.left), abs(r.right), abs(r.top), abs(r.bottom)) for r, _ in rects) + ot + 2)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    mid = size // 2
    if ot:
        oa = int(255 * cfg["outline_opacity"])
        for r, _ in rects:
            pygame.draw.rect(layer, (0, 0, 0, oa), r.move(mid, mid).inflate(2 * ot, 2 * ot))
    for r, op in rects:
        # Linie erst leeren, damit die Outline nicht durchscheint
        layer.fill((0, 0, 0, 0), r.move(mid, mid))
        layer.fill((*color, int(255 * op)), r.move(mid, mid))
    surface.blit(layer, (int(center[0]) - mid, int(center[1]) - mid))
