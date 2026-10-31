"""Umgebung: Himmel, Sonne, Sandboden, Arena-Mauern und Gebaeude im Hintergrund.

Zeichenreihenfolge ist fest und braucht keine Tiefensortierung gegen Bots/Kisten:
Der Spieler und alle Ziele sind immer INNERHALB der (konvexen) Arena. Alles, was
auf der Mauer oder dahinter liegt, ist deshalb immer weiter weg als jedes Ziel und
wird zuerst gezeichnet.
"""
import random

from .world import Cover

SKY_TOP, SKY_HORIZON = (74, 132, 204), (206, 226, 242)
GROUND_NEAR, GROUND_HAZE = (186, 166, 128), (214, 204, 182)
GRID = (170, 150, 112)
SUN, SUN_GLOW = (255, 250, 225), (255, 240, 190)
SUN_DIR = (40.0, 24.0)   # Yaw/Pitch in Grad
WALL, WALL_BASE = (216, 198, 162), (168, 148, 112)
BUILDING_COLORS = [(198, 136, 100), (172, 152, 128), (120, 152, 162), (208, 184, 146), (152, 122, 102)]


class Building(Cover):
    def __init__(self, cx, cz, hx, hz, height, color):
        super().__init__(cx, cz, hx, hz, height, hides=False)
        self.color = color


class Environment:
    def __init__(self, bounds, seed=7):
        rng = random.Random(seed)
        x0, x1, z0, z1 = bounds
        self.bounds = bounds
        self.walls = []        # (Viereck, Farbe) - Innenseiten der Arena-Mauern
        # Jede Mauerseite in Segmente unterschiedlicher Hoehe teilen
        sides = [((x0, z0), (x1, z0)), ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))]
        for (ax, az), (bx, bz) in sides:
            length = abs(bx - ax) + abs(bz - az)
            pos = 0.0
            while pos < length:
                seg = min(length - pos, rng.uniform(6.0, 11.0))
                k0, k1 = pos / length, (pos + seg) / length
                pa = (ax + (bx - ax) * k0, az + (bz - az) * k0)
                pb = (ax + (bx - ax) * k1, az + (bz - az) * k1)
                h = rng.uniform(3.2, 5.2)
                self.walls.append(([(pa[0], 0, pa[1]), (pa[0], h, pa[1]), (pb[0], h, pb[1]), (pb[0], 0, pb[1])], WALL))
                self.walls.append(([(pa[0], 0, pa[1]), (pa[0], 0.6, pa[1]), (pb[0], 0.6, pb[1]), (pb[0], 0, pb[1])],
                                   WALL_BASE))
                pos += seg

        # Gebaeude rund um die Arena (ragen ueber die Mauern)
        self.buildings = []
        for _ in range(60):
            side = rng.randrange(4)
            out = rng.uniform(4.0, 22.0)
            hx, hz = rng.uniform(2.0, 5.0), rng.uniform(2.0, 5.0)
            if side == 0:
                cx, cz = rng.uniform(x0 - 20, x1 + 20), z0 - out - hz
            elif side == 1:
                cx, cz = x1 + out + hx, rng.uniform(z0 - 20, z1 + 20)
            elif side == 2:
                cx, cz = rng.uniform(x0 - 20, x1 + 20), z1 + out + hz
            else:
                cx, cz = x0 - out - hx, rng.uniform(z0 - 20, z1 + 20)
            if any(abs(cx - b.cx) < hx + b.hx + 1 and abs(cz - b.cz) < hz + b.hz + 1 for b in self.buildings):
                continue
            self.buildings.append(Building(cx, cz, hx, hz, rng.uniform(7.0, 20.0), rng.choice(BUILDING_COLORS)))
