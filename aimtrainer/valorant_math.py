"""Valorant-Sensitivity- und FOV-Mathematik.

Valorant (UE4) rechnet Mausbewegung linear und ohne Beschleunigung/Smoothing:

    Winkel [Grad] = Counts * Sens * 0.07

0.07 ist der Yaw/Pitch-Multiplikator von Valorant (Grad pro Count bei Sens 1.0).
Yaw und Pitch nutzen denselben Faktor. Die Ingame-FOV ist auf 103 Grad
horizontal (bezogen auf 16:9) fixiert und hat KEINEN Einfluss auf die
Rotation pro Count - sie bestimmt nur, wie die Welt auf den Bildschirm projiziert wird.
"""
import math

VALORANT_YAW = 0.07          # Grad pro Count bei Sens 1.0 (gilt auch fuer Pitch)
VALORANT_HFOV = 103.0        # horizontale FOV bei 16:9
VALORANT_ASPECT = 16.0 / 9.0
INCH_TO_CM = 2.54


def deg_per_count(sens: float) -> float:
    return VALORANT_YAW * sens


def cm_per_360(sens: float, dpi: float) -> float:
    """Wie viele cm Mausweg fuer eine volle 360-Grad-Drehung."""
    counts_per_360 = 360.0 / deg_per_count(sens)
    return counts_per_360 / dpi * INCH_TO_CM


def sens_from_cm_per_360(cm: float, dpi: float) -> float:
    return 360.0 / (VALORANT_YAW * dpi * cm / INCH_TO_CM)


def edpi(sens: float, dpi: float) -> float:
    return sens * dpi


def vfov_from_hfov(hfov_deg: float, aspect: float) -> float:
    """Vertikale FOV aus horizontaler FOV: tan(v/2) = tan(h/2) / aspect."""
    return math.degrees(2.0 * math.atan(math.tan(math.radians(hfov_deg) / 2.0) / aspect))


def focal_length_px(screen_width_px: int, hfov_deg: float = VALORANT_HFOV) -> float:
    """Brennweite in Pixeln fuer die Perspektivprojektion: x_screen = f * x/z."""
    return (screen_width_px / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


def wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


# Valorant vertikale FOV bei 16:9 ~= 70.53 Grad
VALORANT_VFOV = vfov_from_hfov(VALORANT_HFOV, VALORANT_ASPECT)
