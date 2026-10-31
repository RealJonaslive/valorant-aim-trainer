"""Arena fuer den Peek-Modus: Deckungsobjekte (achsenparallele Boxen), Kollision
des Spielers, Sichtlinien- und Schuss-Verdeckung.
"""
import math

from .bots import _ray_obb

AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
PLAYER_RADIUS = 0.4
BOUNDS = (-25.0, 25.0, -8.0, 38.0)   # x_min, x_max, z_min, z_max


class Cover:
    def __init__(self, cx, cz, hx, hz, height, hides=True):
        self.cx, self.cz, self.hx, self.hz, self.height = cx, cz, hx, hz, height
        self.hides = hides   # hoch genug, dass sich ein Bot komplett dahinter verstecken kann

    @property
    def center(self):
        return (self.cx, self.height / 2, self.cz)

    @property
    def half(self):
        return (self.hx, self.height / 2, self.hz)

    def ray(self, origin, d):
        return _ray_obb(origin, d, self.center, self.half, AXES)

    def nearest_dist(self, p):
        """Abstand eines Punkts zur Box (fuer die Zeichenreihenfolge)."""
        dx = max(abs(p[0] - self.cx) - self.hx, 0.0)
        dy = max(abs(p[1] - self.height / 2) - self.height / 2, 0.0)
        dz = max(abs(p[2] - self.cz) - self.hz, 0.0)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def blocks_circle(self, x, z, r):
        return abs(x - self.cx) < self.hx + r and abs(z - self.cz) < self.hz + r


def generate_covers(rng, count=7, low=2):
    """Zufaelliges Layout vor dem Spawn: hohe Deckungen (Bots verstecken sich) + niedrige Kisten."""
    covers = []
    tries = 0
    while len(covers) < count + low and tries < 2000:
        tries += 1
        hides = len(covers) < count
        cx, cz = rng.uniform(-13, 13), rng.uniform(9, 32)
        hx, hz = rng.uniform(0.6, 1.6), rng.uniform(0.5, 1.0)
        h = rng.uniform(2.0, 2.6) if hides else rng.uniform(0.9, 1.1)
        if math.hypot(cx, cz) < 8:
            continue
        if any(abs(cx - c.cx) < hx + c.hx + 3.5 and abs(cz - c.cz) < hz + c.hz + 3.5 for c in covers):
            continue
        covers.append(Cover(cx, cz, hx, hz, h, hides))
    return covers


def first_block(covers, origin, d, max_t=math.inf):
    """Distanz zum ersten Deckungsobjekt entlang des Strahls (oder inf)."""
    best = math.inf
    for c in covers:
        t = c.ray(origin, d)
        if t is not None and t < best:
            best = t
    return best if best < max_t else math.inf


def line_of_sight(covers, a, b):
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1e-9
    return first_block(covers, a, (d[0] / n, d[1] / n, d[2] / n), n) == math.inf


def move_player(pos, vx, vz, dt, covers):
    """Achsenweise bewegen, bei Kollision die jeweilige Achse blockieren (Gleiten an Waenden)."""
    x, y, z = pos
    nx = min(BOUNDS[1], max(BOUNDS[0], x + vx * dt))
    if any(c.blocks_circle(nx, z, PLAYER_RADIUS) for c in covers):
        nx = x
    nz = min(BOUNDS[3], max(BOUNDS[2], z + vz * dt))
    if any(c.blocks_circle(nx, nz, PLAYER_RADIUS) for c in covers):
        nz = z
    return (nx, y, nz)
