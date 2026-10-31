"""Uebungs-Bots: humanoide Puppe aus Boxen + Kugelkopf (eigenes Design).

Bot.pos ist immer der KOPF-Mittelpunkt - darauf beziehen sich Analyse und
Fehlerwinkel. Der Koerper wird darunter bis zum Boden aufgebaut und dreht sich
immer zur Kamera (wie eine Trainingspuppe, die dich ansieht).

Treffer: Kopf = Kill (Headshot). Koerper = Koerpertreffer, kein Kill.
"""
import math

HEAD_RADIUS = 0.115   # Kopf ~23 cm breit
STAND_HEAD_Y = 1.6

# (Name, lokale Mitte x/y-Offset zur Hueft-/Kopfreferenz, Halbmasse) - y relativ zum Kopf
# Beine werden separat bis zum Boden gestreckt.
UPPER_PARTS = (
    ("neck", (0.0, -0.14), (0.05, 0.04, 0.05)),
    ("torso", (0.0, -0.45), (0.21, 0.27, 0.12)),
    ("arm_l", (-0.28, -0.48), (0.06, 0.28, 0.07)),
    ("arm_r", (0.28, -0.48), (0.06, 0.28, 0.07)),
)
HIP_BELOW_HEAD = 0.72


class Bot:
    def __init__(self, pos, radius=HEAD_RADIUS):
        self.pos = list(pos)
        self.radius = radius
        self.alive = True
        self.flash_until = 0.0   # kurzes Aufleuchten bei Koerpertreffer

    def boxes(self, cam_pos):
        """Orientierte Boxen (Name, Mitte, Halbmasse, Achsen) - Front zur Kamera gedreht."""
        dx, dz = cam_pos[0] - self.pos[0], cam_pos[2] - self.pos[2]
        n = math.hypot(dx, dz) or 1.0
        fwd = (dx / n, 0.0, dz / n)
        right = (fwd[2], 0.0, -fwd[0])
        up = (0.0, 1.0, 0.0)
        axes = (right, up, fwd)
        hx, hy, hz = self.pos
        out = []
        for name, (ox, oy), half in UPPER_PARTS:
            c = (hx + right[0] * ox, hy + oy, hz + right[2] * ox)
            out.append((name, c, half, axes))
        hip = max(0.2, hy - HIP_BELOW_HEAD)
        for name, ox in (("leg_l", -0.1), ("leg_r", 0.1)):
            c = (hx + right[0] * ox, hip / 2, hz + right[2] * ox)
            out.append((name, c, (0.075, hip / 2, 0.09), axes))
        return out

    def raycast(self, origin, d):
        """Naechster Treffer entlang des Strahls: (Distanz, 'head'|'body') oder None."""
        best = None
        t = _ray_sphere(origin, d, self.pos, self.radius)
        if t is not None:
            best = (t, "head")
        for _, c, half, axes in self.boxes(origin):
            t = _ray_obb(origin, d, c, half, axes)
            if t is not None and (best is None or t < best[0]):
                best = (t, "body")
        return best


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _ray_sphere(o, d, c, r):
    oc = (c[0] - o[0], c[1] - o[1], c[2] - o[2])
    tc = _dot(oc, d)
    if tc <= 0:
        return None
    h = _dot(oc, oc) - tc * tc
    if h > r * r:
        return None
    return tc - math.sqrt(r * r - h)


def _ray_obb(o, d, c, half, axes):
    """Slab-Test in Box-Koordinaten."""
    rel = (o[0] - c[0], o[1] - c[1], o[2] - c[2])
    t0, t1 = 0.0, math.inf
    for ax, h in zip(axes, half):
        oo, dd = _dot(rel, ax), _dot(d, ax)
        if abs(dd) < 1e-12:
            if abs(oo) > h:
                return None
            continue
        a, b = (-h - oo) / dd, (h - oo) / dd
        if a > b:
            a, b = b, a
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1:
            return None
    return t0 if t0 > 0 else None
