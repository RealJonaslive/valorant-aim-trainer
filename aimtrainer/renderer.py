"""Software-3D mit pygame: eigene Perspektivprojektion mit exakt 103 Grad hFOV.

Bewusst ohne OpenGL-Abhaengigkeit: Bots bestehen aus wenigen Boxen + Kugelkopf,
dafuer reicht Eckpunkt-Projektion + konvexe Huelle, und die FOV-Mathematik bleibt
komplett sichtbar.

Zeichenreihenfolge: Himmel -> Sonne -> Boden -> Raster -> Gebaeude -> Arena-Mauern
-> Kisten/Bots (nach Abstand sortiert).
"""
import math

import pygame

from . import crosshair
from . import environment as env_style
from .modes import DEATH_TIME
from .valorant_math import VALORANT_HFOV, focal_length_px

NEAR = 0.05
BOT_TORSO, BOT_LIMB, BOT_EDGE = (78, 92, 126), (62, 74, 102), (28, 32, 44)
HEAD, HEAD_EDGE = (255, 196, 48), (90, 60, 10)
FLASH, DEAD, DEAD_EDGE = (255, 255, 255), (120, 120, 126), (60, 60, 64)
CRATE = (128, 92, 58)
HUD_BG = (12, 14, 20, 170)


def _shade(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


def _hull(pts):
    """Konvexe Huelle (Monotone Chain) der projizierten Box-Ecken."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


class Renderer:
    _fonts = None
    grid_lines = [((x, 0, -60), (x, 0, 60)) for x in range(-60, 61, 4)] + \
                 [((-60, 0, z), (60, 0, z)) for z in range(-60, 61, 4)]

    def __init__(self, screen, hfov=VALORANT_HFOV):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.cx, self.cy = self.w / 2, self.h / 2
        self.f = focal_length_px(self.w, hfov)   # gleiche Brennweite fuer x und y (quadratische Pixel)
        if not Renderer._fonts:   # SysFont-Suche ist langsam -> einmal pro Prozess
            Renderer._fonts = (pygame.font.SysFont("segoeui", 17, bold=True),
                               pygame.font.SysFont("segoeui", 26, bold=True))
        self.font, self.big = Renderer._fonts
        # Verlaeufe einmal vorberechnen (1x2-Bild weich hochskaliert = linearer Verlauf)
        self.sky = self._gradient(env_style.SKY_TOP, env_style.SKY_HORIZON, int(self.h * 0.9))
        self.ground = self._gradient(env_style.GROUND_HAZE, env_style.GROUND_NEAR, int(self.h * 0.5))

    def _gradient(self, top, bottom, height):
        src = pygame.Surface((1, 2))
        src.set_at((0, 0), top)
        src.set_at((0, 1), bottom)
        return pygame.transform.smoothscale(src, (max(1, self.w), max(2, height)))

    def project(self, pc):
        return self.cx + self.f * pc[0] / pc[2], self.cy - self.f * pc[1] / pc[2]

    def _planes(self):
        tx, ty = self.cx / self.f * 1.01, self.cy / self.f * 1.01
        return (lambda p: p[2] - NEAR,
                lambda p: tx * p[2] - p[0], lambda p: tx * p[2] + p[0],
                lambda p: ty * p[2] - p[1], lambda p: ty * p[2] + p[1])

    def _line(self, cam, basis, a, b, color):
        """Liang-Barsky-Clipping gegen Near-Plane und die 4 Seitenflaechen des Frustums,
        damit pygame nie riesige Off-Screen-Koordinaten zeichnen muss."""
        pa, pb = cam.to_camera_space(a, basis), cam.to_camera_space(b, basis)
        t0, t1 = 0.0, 1.0
        for pl in self._planes():
            da, db = pl(pa), pl(pb)
            if da < 0 and db < 0:
                return
            if da < 0:
                t0 = max(t0, da / (da - db))
            elif db < 0:
                t1 = min(t1, da / (da - db))
        if t0 >= t1:
            return
        lerp = lambda k: tuple(pa[i] + (pb[i] - pa[i]) * k for i in range(3))  # noqa: E731
        pygame.draw.line(self.screen, color, self.project(lerp(t0)), self.project(lerp(t1)))

    def _clip_poly(self, pts):
        """Sutherland-Hodgman gegen Near-Plane + Frustum-Seiten (Kameraraum)."""
        for pl in self._planes():
            if not pts:
                return pts
            out = []
            for i, a in enumerate(pts):
                b = pts[(i + 1) % len(pts)]
                da, db = pl(a), pl(b)
                if da >= 0:
                    out.append(a)
                if (da >= 0) != (db >= 0):
                    k = da / (da - db)
                    out.append(tuple(a[j] + (b[j] - a[j]) * k for j in range(3)))
            pts = out
        return pts

    def _quad(self, cam, basis, pts, color, edge=None):
        poly = self._clip_poly([cam.to_camera_space(q, basis) for q in pts])
        if len(poly) >= 3:
            scr = [self.project(q) for q in poly]
            pygame.draw.polygon(self.screen, color, scr)
            if edge:
                pygame.draw.polygon(self.screen, edge, scr, 1)

    # ------------------------------------------------------------------ Welt
    def _draw_backdrop(self, cam, basis, env):
        fwd = basis[0]
        horizon = cam.to_camera_space((cam.pos[0] + fwd[0] * 1e4, cam.pos[1], cam.pos[2] + fwd[2] * 1e4), basis)
        hy = self.project(horizon)[1] if horizon[2] > NEAR else (0 if cam.pitch < 0 else self.h)
        hy = int(max(-1, min(self.h + 1, hy)))
        # Himmel (Verlauf endet am Horizont) und Boden (Dunst am Horizont -> satter nach vorne)
        self.screen.fill(env_style.SKY_TOP)
        self.screen.blit(self.sky, (0, hy - self.sky.get_height()))
        self.screen.fill(env_style.GROUND_NEAR, (0, hy, self.w, self.h - hy))
        self.screen.blit(self.ground, (0, hy))
        # Sonne
        sy, sp = map(math.radians, env_style.SUN_DIR)
        sun = (cam.pos[0] + math.sin(sy) * math.cos(sp) * 1e3, cam.pos[1] + math.sin(sp) * 1e3,
               cam.pos[2] + math.cos(sy) * math.cos(sp) * 1e3)
        sc = cam.to_camera_space(sun, basis)
        if sc[2] > NEAR:
            x, y = self.project(sc)
            if -100 < x < self.w + 100 and -100 < y < self.h + 100:
                pygame.draw.circle(self.screen, env_style.SUN_GLOW, (x, y), self.f * 0.05)
                pygame.draw.circle(self.screen, env_style.SUN, (x, y), self.f * 0.032)
        for a, b in self.grid_lines:
            self._line(cam, basis, a, b, env_style.GRID)
        if env is None:
            return
        for b in sorted(env.buildings, key=lambda b: -b.nearest_dist(cam.pos)):
            self.draw_box(cam, basis, b, b.color, edge=_shade(b.color, 0.7))
        for pts, color in env.walls:
            self._quad(cam, basis, pts, color, _shade(color, 0.8))

    def draw_world(self, cam, targets, dead=(), now=0.0, covers=(), env=None):
        basis = cam.basis()
        self._draw_backdrop(cam, basis, env)
        # Maler-Algorithmus: alles nach Abstand sortieren, hinten zuerst. Fuer Boxen zaehlt
        # der naechste Punkt der Box - so wird ein Bot hinter einer Deckung korrekt verdeckt.
        items = []
        for bot in targets:
            items.append((math.dist(cam.pos, bot.pos), "bot", bot, None))
        for bot, td in dead:
            if now - td < DEATH_TIME:
                items.append((math.dist(cam.pos, bot.pos), "bot", bot, td))
        for c in covers:
            items.append((c.nearest_dist(cam.pos), "box", c, None))
        items.sort(key=lambda it: -it[0])
        for _, kind, obj, td in items:
            if kind == "box":
                self.draw_box(cam, basis, obj, CRATE, edge=_shade(CRATE, 0.5))
                continue
            squash = 1.0 if td is None else max(0.05, 1.0 - (now - td) / DEATH_TIME)
            self.draw_bot(cam, basis, obj, flashing=now < obj.flash_until, dead=td is not None, squash=squash)

    def draw_box(self, cam, basis, c, color, edge=None):
        """Sichtbare Seiten einer achsenparallelen Box, je nach Richtung schattiert."""
        x0, x1, z0, z1, h = c.cx - c.hx, c.cx + c.hx, c.cz - c.hz, c.cz + c.hz, c.height
        p = cam.pos
        faces = []
        if p[1] > h:
            faces.append(([(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)], 1.15))
        if p[0] < x0:
            faces.append(([(x0, 0, z0), (x0, h, z0), (x0, h, z1), (x0, 0, z1)], 0.8))
        if p[0] > x1:
            faces.append(([(x1, 0, z0), (x1, h, z0), (x1, h, z1), (x1, 0, z1)], 0.8))
        if p[2] < z0:
            faces.append(([(x0, 0, z0), (x1, 0, z0), (x1, h, z0), (x0, h, z0)], 1.0))
        if p[2] > z1:
            faces.append(([(x0, 0, z1), (x1, 0, z1), (x1, h, z1), (x0, h, z1)], 0.9))
        for pts, k in faces:
            self._quad(cam, basis, pts, _shade(color, k), edge)

    def draw_bot(self, cam, basis, bot, flashing=False, dead=False, squash=1.0):
        """Bot zeichnen; squash < 1 laesst ihn nach dem Kill in den Boden sacken."""
        def cs(p):
            return cam.to_camera_space((p[0], p[1] * squash, p[2]), basis)

        parts = []
        for name, c, half, axes in bot.boxes(cam.pos):
            corners = []
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        corners.append(cs(tuple(c[i] + sx * half[0] * axes[0][i] + sy * half[1] * axes[1][i]
                                                + sz * half[2] * axes[2][i] for i in range(3))))
            if min(p[2] for p in corners) < NEAR:
                continue
            depth = sum(p[2] for p in corners) / 8
            color = BOT_TORSO if name in ("torso", "neck") else BOT_LIMB
            parts.append((depth, [self.project(p) for p in corners], color))
        for _, pts, color in sorted(parts, key=lambda p: -p[0]):
            hull = _hull(pts)
            if len(hull) >= 3:
                fill = DEAD if dead else (FLASH if flashing else color)
                pygame.draw.polygon(self.screen, fill, hull)
                pygame.draw.polygon(self.screen, DEAD_EDGE if dead else BOT_EDGE, hull, 1)
        hc = cs(bot.pos)
        if hc[2] > NEAR:
            x, y = self.project(hc)
            r = max(1.5, self.f * bot.radius / hc[2])
            pygame.draw.circle(self.screen, DEAD if dead else HEAD, (x, y), r)
            pygame.draw.circle(self.screen, DEAD_EDGE if dead else HEAD_EDGE, (x, y), r, 1)

    def draw_crosshair(self, cfg, firing=False):
        crosshair.draw(self.screen, (self.cx, self.cy), cfg, firing)

    # ------------------------------------------------------------------ HUD
    def label(self, text, pos, big=False, color=(240, 240, 245), anchor="topleft", pad=(12, 6)):
        """Text auf halbtransparentem Kasten - lesbar vor hellem Himmel und dunklem Boden."""
        img = (self.big if big else self.font).render(text, True, color)
        box = pygame.Rect(0, 0, img.get_width() + 2 * pad[0], img.get_height() + 2 * pad[1])
        setattr(box, anchor, pos)
        bg = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, HUD_BG, bg.get_rect(), border_radius=8)
        self.screen.blit(bg, box)
        self.screen.blit(img, (box.x + pad[0], box.y + pad[1]))
        return box
