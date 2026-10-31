"""Trainingsmodi. Alle Distanzen in Metern (Valorant: 1 UE-Unit = 1 cm).

Ziele sind Uebungs-Bots (siehe bots.py). Kopf-Mittelpunkt auf ~1.6 m = Augenhoehe
der Kamera -> korrektes Crosshair-Placement liegt auf der Horizontlinie.
Kopf = Kill, Koerper = Koerpertreffer (zaehlt fuer die Analyse als Fehlschuss).
Valorant-Laufgeschwindigkeit: 6.75 m/s.
"""
import math
import random

from .bots import STAND_HEAD_Y, Bot
from .valorant_math import wrap180
from .world import first_block, generate_covers, line_of_sight, move_player

RUN_SPEED = 6.75
WALK_SPEED = 3.0          # langsames Peeken
MOVE_ACCEL = 60.0         # m/s^2 - Valorant beschleunigt sehr schnell
ACCURATE_SPEED = 1.35     # darunter volle Genauigkeit (Annaeherung an Valorant)
MAX_MOVE_SPREAD = 4.0     # Grad Streuung bei voller Laufgeschwindigkeit
DEATH_TIME = 0.35   # so lange faellt ein getoeteter Bot sichtbar um

MODE_INFO = {
    "flick": ("Flick",
              "Ein Bot erscheint plötzlich 4–30° neben deinem Fadenkreuz (8–30 m). "
              "Flick auf den Kopf und schieß. Bester Modus für die Sens-Analyse."),
    "gridshot": ("Multi-Bot",
                 "Drei Bots stehen gleichzeitig in einer Reihe (8–16 m). Nach jedem Kill "
                 "erscheint ein neuer. Trainiert schnelle Zielwechsel."),
    "tracking": ("Tracking",
                 "Ein Bot läuft A-D hin und her (Valorant-Laufgeschwindigkeit). Halte das "
                 "Fadenkreuz auf seinem Kopf. Misst Mitziehen, Verzögerung und Zittern."),
    "peek": ("Peek (Bewegung)",
             "Lauf mit WASD durch eine Arena. Bots verstecken sich hinter Kisten und peeken "
             "zufällig mal knapp, mal weit raus. Zum Schießen stehen bleiben."),
}


MODE_TIPS = {
    "flick": [
        "Lass das Fadenkreuz in der Mitte ruhig stehen und warte, bis eine Figur auftaucht.",
        "Zieh in EINER schnellen Bewegung zum Kopf – nicht in vielen kleinen Schritten.",
        "Klick erst, wenn du wirklich auf dem Kopf bist. Genauigkeit ist wichtiger als Tempo.",
    ],
    "gridshot": [
        "Schieß die Figuren nacheinander ab, ohne lange zu überlegen.",
        "Schau schon zum nächsten Kopf, während du klickst.",
        "Bleib locker – ein verkrampfter Griff macht dich langsamer.",
    ],
    "tracking": [
        "Folge dem Kopf mit einer ruhigen, gleichmäßigen Bewegung.",
        "Wechselt die Figur die Richtung, reagiere ruhig statt hektisch nachzuziehen.",
        "Halte das Handgelenk locker. Zittern kostet mehr als ein kleiner Abstand.",
    ],
    "peek": [
        "Halte das Fadenkreuz immer auf Kopfhöhe – direkt an der Kante der Kiste.",
        "Bleib stehen, bevor du schießt (W A S D loslassen). Im Laufen gehen Schüsse daneben.",
        "Figuren kommen mal nur ein kleines Stück, mal weit heraus. Warte nicht auf einer festen Stelle.",
    ],
}

GENERAL_TIPS = [
    "Spiel dich ein paar Minuten warm, bevor du auf die Empfehlung achtest.",
    "Sitz entspannt, Ellbogen und Handgelenk locker.",
    "Esc drücken = Pause. Dort kannst du weiterspielen oder beenden.",
]


def head_position(cam, yaw_deg, horiz_dist, head_y=STAND_HEAD_Y):
    y = math.radians(yaw_deg)
    return (cam.pos[0] + horiz_dist * math.sin(y), head_y, cam.pos[2] + horiz_dist * math.cos(y))


class StaticTrial:
    """Ein Flick: von Spawn (bzw. letztem Kill) bis zum Kopftreffer.

    Waehrend des Trials wird nur die absolute Blickrichtung gespeichert; welches
    Ziel gemeint war, steht erst am Ende fest (Multi-Bot). finalize() rechnet dann
    alles in Fehlerwinkel 'Ziel - Fadenkreuz' um.
    """

    def __init__(self, t0, mode):
        self.t0, self.mode = t0, mode
        self.cam_samples = []   # (t, yaw, pitch)
        self.clicks = []        # (t, hit)

    def sample(self, t, cam):
        self.cam_samples.append((t - self.t0, cam.yaw, cam.pitch))

    def finalize(self, cam, target, result):
        ty, tp = cam.angles_to(target.pos)
        c = math.cos(math.radians(tp))
        dist = math.dist(cam.pos, target.pos)
        return {
            "mode": self.mode,
            "result": result,
            "distance_m": round(dist, 3),
            "target_radius_deg": round(math.degrees(math.asin(min(1.0, target.radius / dist))), 5),
            "samples": [[round(t, 5), round(wrap180(ty - y) * c, 5), round(tp - p, 5)]
                        for t, y, p in self.cam_samples],
            "clicks": [[round(t - self.t0, 5), h] for t, h in self.clicks],
        }


class Mode:
    name = "base"

    def __init__(self, cam, rng=None):
        self.cam = cam
        self.rng = rng or random.Random()
        self.targets = []
        self.dead = []            # (bot, Todeszeit) fuer die Umfall-Animation
        self.trials = []          # fertige Trials (dicts)
        self.tracking = []        # Tracking-Samples
        self.kills = 0
        self.shots = 0
        self.body_hits = 0

    def on_input(self, t):       # nach jeder Rohbewegung
        pass

    def on_click(self, t):
        pass

    def update(self, t, dt):     # einmal pro Frame
        pass

    def shoot(self, t, direction=None, covers=()):
        """Strahl vom Fadenkreuz -> (Bot, 'head'|'body') des naechsten Treffers oder (None, None).
        Deckungsobjekte blockieren den Schuss (keine Wallbangs)."""
        self.shots += 1
        d = direction or self.cam.basis()[0]
        best = (first_block(covers, self.cam.pos, d), None, None)
        for bot in self.targets:
            if bot.alive and (hit := bot.raycast(self.cam.pos, d)) and hit[0] < best[0]:
                best = (hit[0], bot, hit[1])
        _, bot, part = best
        if part == "body":
            self.body_hits += 1
            bot.flash_until = t + 0.08
        return bot, part

    def _kill(self, bot, t):
        bot.alive = False
        self.kills += 1
        self.dead.append((bot, t))
        self.dead = [(b, td) for b, td in self.dead if t - td < DEATH_TIME]


class FlickMode(Mode):
    """Ein Bot erscheint nach zufaelliger Pause 4-30 Grad neben dem Fadenkreuz in 8-30 m."""
    name = "flick"

    def __init__(self, cam, rng=None, min_deg=4.0, max_deg=30.0, timeout=2.5):
        super().__init__(cam, rng)
        self.min_deg, self.max_deg, self.timeout = min_deg, max_deg, timeout
        self.trial = None
        self.next_spawn = None

    def _spawn(self, t):
        off = self.rng.uniform(self.min_deg, self.max_deg) * self.rng.choice((-1, 1))
        dist = self.rng.uniform(8.0, 30.0)
        head_y = STAND_HEAD_Y + self.rng.uniform(-0.12, 0.12)   # leichte Hoehenvariation
        self.targets = [Bot(head_position(self.cam, self.cam.yaw + off, dist, head_y))]
        self.trial = StaticTrial(t, self.name)
        self.trial.sample(t, self.cam)

    def on_input(self, t):
        if self.trial:
            self.trial.sample(t, self.cam)

    def on_click(self, t):
        bot, part = self.shoot(t)
        if not self.trial:
            return
        self.trial.clicks.append((t, part == "head"))
        if part == "head":
            self._kill(bot, t)
            self._end(t, "hit")

    def _end(self, t, result):
        self.trials.append(self.trial.finalize(self.cam, self.targets[0], result))
        self.trial, self.targets = None, []
        self.next_spawn = t + self.rng.uniform(0.35, 0.9)  # zufaellig -> keine Antizipation

    def update(self, t, dt):
        if self.next_spawn is None:
            self.next_spawn = t + 1.0
        if self.trial is None and t >= self.next_spawn:
            self._spawn(t)
        elif self.trial and t - self.trial.t0 > self.timeout:
            self._end(t, "timeout")


class GridshotMode(Mode):
    """3 Bots gleichzeitig auf 5 Spalten x 3 Entfernungen. Jeder Kill startet den
    naechsten Trial; der getoetete Bot definiert nachtraeglich den Flick."""
    name = "gridshot"

    def __init__(self, cam, rng=None, spacing_deg=7.0, count=3):
        super().__init__(cam, rng)
        self.cells = [(cx * spacing_deg, d) for cx in range(-2, 3) for d in (8.0, 12.0, 16.0)]
        self.count = count
        self.cell_of = {}
        self.trial = None

    def _spawn_one(self):
        used_cols = {c[0] for c in self.cell_of.values()}
        free = [c for c in self.cells if c[0] not in used_cols]   # nie zwei Bots hintereinander
        cell = self.rng.choice(free)
        bot = Bot(head_position(self.cam, cell[0], cell[1]))
        self.targets.append(bot)
        self.cell_of[id(bot)] = cell

    def on_input(self, t):
        if self.trial:
            self.trial.sample(t, self.cam)

    def on_click(self, t):
        bot, part = self.shoot(t)
        self.trial.clicks.append((t, part == "head"))
        if part != "head":
            return
        self._kill(bot, t)
        self.trials.append(self.trial.finalize(self.cam, bot, "hit"))
        self.targets.remove(bot)
        self.cell_of.pop(id(bot))
        self._spawn_one()
        self.trial = StaticTrial(t, self.name)
        self.trial.sample(t, self.cam)

    def update(self, t, dt):
        if self.trial is None:
            self.cam.yaw, self.cam.pitch = 0.0, 0.0
            for _ in range(self.count):
                self._spawn_one()
            self.trial = StaticTrial(t, self.name)


class TrackingMode(Mode):
    """Ein Bot strafet ADAD-artig mit Valorant-Laufgeschwindigkeit in 12 m.
    Richtungswechsel zufaellig alle 0.15-0.9 s, gelegentliche Stopps (Counter-Strafe).
    Gemessen wird kontinuierlich; Schiessen zaehlt Kopftreffer."""
    name = "tracking"

    def __init__(self, cam, rng=None, dist=12.0, lane=4.0, accel_time=0.06):
        super().__init__(cam, rng)
        self.dist, self.lane, self.accel_time = dist, lane, accel_time
        self.targets = [Bot((0.0, STAND_HEAD_Y, dist))]
        self.vel = 0.0
        self.dir = 1
        self.goal_vel = RUN_SPEED
        self.next_change = 0.0
        self.head_hits = 0

    def on_click(self, t):
        _, part = self.shoot(t)
        self.head_hits += part == "head"
        self.kills = self.head_hits   # HUD zeigt Kopftreffer

    def update(self, t, dt):
        tg = self.targets[0]
        if t >= self.next_change:
            if self.goal_vel != 0.0 and self.rng.random() < 0.15:
                self.goal_vel = 0.0                       # kurzer Stopp
            else:
                self.dir = -self.dir                      # A <-> D
                self.goal_vel = RUN_SPEED * self.dir
            self.next_change = t + self.rng.uniform(0.15, 0.9)
        if abs(tg.pos[0]) > self.lane and tg.pos[0] * self.goal_vel > 0:
            self.dir = -self.dir
            self.goal_vel = RUN_SPEED * self.dir
        step = RUN_SPEED / self.accel_time * dt
        self.vel += max(-step, min(step, self.goal_vel - self.vel))
        tg.pos[0] += self.vel * dt

        on = self.cam.ray_hits_sphere(tg.pos, tg.radius)
        ex, ey = self.cam.angular_error_to(tg.pos)
        ty, _ = self.cam.angles_to(tg.pos)
        self.tracking.append([round(t, 5), round(ex, 5), round(ey, 5), round(ty, 5), int(on)])


class PeekMode(Mode):
    """Bewegung + Deckung. Jeder Bot gehoert zu einer Deckung und durchlaeuft:

        wait (versteckt) -> out (peekt seitlich raus) -> hold (haelt den Winkel) -> back -> wait

    Alles zufaellig: Seite, wie weit (knapp an der Kante / mittel / weiter Swing),
    Tempo (laufen / langsam), Haltezeit, Jiggle-Peeks (sofort wieder zurueck).
    Die Versteck- und Peek-Punkte werden bei jedem Peek relativ zu deiner AKTUELLEN
    Position berechnet - Deckung schuetzt also immer vor dir, und du kannst nicht
    einfach auf eine feste Stelle vorzielen.
    """
    name = "peek"

    def __init__(self, cam, rng=None, bots=2):
        super().__init__(cam, rng)
        self.covers = generate_covers(self.rng)
        self.n_bots = bots
        self.vel = [0.0, 0.0]
        self.peeks = []            # abgeschlossene Peek-Ereignisse
        self.moving_shots = 0
        self.respawns = []
        self.started = False

    # ---------------------------------------------------------- Bewegung
    def move(self, forward, strafe, dt):
        """forward/strafe in {-1, 0, 1} aus WASD."""
        y = math.radians(self.cam.yaw)
        fx, fz, rx, rz = math.sin(y), math.cos(y), math.cos(y), -math.sin(y)
        wx, wz = fx * forward + rx * strafe, fz * forward + rz * strafe
        n = math.hypot(wx, wz)
        wx, wz = (wx / n * RUN_SPEED, wz / n * RUN_SPEED) if n else (0.0, 0.0)
        dvx, dvz = wx - self.vel[0], wz - self.vel[1]
        dn = math.hypot(dvx, dvz)
        step = MOVE_ACCEL * dt
        if dn > step:
            dvx, dvz = dvx / dn * step, dvz / dn * step
        self.vel[0] += dvx
        self.vel[1] += dvz
        new = move_player(self.cam.pos, self.vel[0], self.vel[1], dt, self.covers)
        if new[0] == self.cam.pos[0]:
            self.vel[0] = 0.0
        if new[2] == self.cam.pos[2]:
            self.vel[1] = 0.0
        self.cam.pos = new

    @property
    def speed(self):
        return math.hypot(*self.vel)

    # ---------------------------------------------------------- Bots
    def _spawn_bot(self, t):
        used = {id(b.cover) for b in self.targets}
        free = [c for c in self.covers if c.hides and id(c) not in used]
        if not free:
            return
        bot = Bot((0.0, STAND_HEAD_Y, 0.0))
        bot.cover = self.rng.choice(free)
        hide, _, _ = self._geometry(bot)
        bot.pos[0], bot.pos[2] = hide
        bot.state, bot.timer, bot.event, bot.visible = "wait", t + self.rng.uniform(0.6, 2.5), None, False
        # Startwerte, falls du den Bot schon vor seinem ersten Peek siehst (z. B. beim Umlaufen)
        bot.hide, bot.peek, bot.speed, bot.jiggle = hide, hide, RUN_SPEED, False
        self.targets.append(bot)

    def _geometry(self, bot):
        """Versteckpunkt hinter der Deckung (von dir aus gesehen) und Seitenrichtung."""
        c, p = bot.cover, self.cam.pos
        dx, dz = c.cx - p[0], c.cz - p[2]
        n = math.hypot(dx, dz) or 1.0
        d = (dx / n, dz / n)
        lat = (d[1], -d[0])
        ext_d = abs(d[0]) * c.hx + abs(d[1]) * c.hz
        ext_l = abs(lat[0]) * c.hx + abs(lat[1]) * c.hz
        hide = (c.cx + d[0] * (ext_d + 0.5), c.cz + d[1] * (ext_d + 0.5))
        return hide, lat, ext_l

    def _start_peek(self, bot):
        hide, lat, ext_l = self._geometry(bot)
        if not bot.visible:          # nur umsetzen, wenn du es nicht siehst
            bot.pos[0], bot.pos[2] = hide
        side = self.rng.choice((-1, 1))
        r = self.rng.random()
        if r < 0.4:
            amount = self.rng.uniform(0.15, 0.7)     # knapp an der Kante
        elif r < 0.8:
            amount = self.rng.uniform(0.7, 1.8)      # normaler Peek
        else:
            amount = self.rng.uniform(1.8, 3.5)      # weiter Swing
        off = side * (ext_l + 0.35 + amount)         # 0.35 = halbe Schulterbreite
        bot.hide = (bot.pos[0], bot.pos[2])
        bot.peek = (hide[0] + lat[0] * off, hide[1] + lat[1] * off)
        bot.speed = RUN_SPEED if self.rng.random() < 0.7 else WALK_SPEED
        bot.jiggle = self.rng.random() < 0.25
        bot.state = "out"

    def _walk(self, bot, goal, dt):
        dx, dz = goal[0] - bot.pos[0], goal[1] - bot.pos[2]
        n = math.hypot(dx, dz)
        step = bot.speed * dt
        if n <= step:
            bot.pos[0], bot.pos[2] = goal
            return True
        bot.pos[0] += dx / n * step
        bot.pos[2] += dz / n * step
        return False

    def _close_event(self, bot, killed, t):
        ev = bot.event
        if ev is None:
            return
        ev["killed"] = killed
        ev["reaction"] = round(t - ev["t_vis"], 4) if killed else None
        self.peeks.append(ev)
        bot.event = None

    def update(self, t, dt):
        if not self.started:
            self.started = True
            for _ in range(self.n_bots):
                self._spawn_bot(t)
        for rt in [r for r in self.respawns if r <= t]:
            self.respawns.remove(rt)
            self._spawn_bot(t)

        for bot in self.targets:
            if bot.state == "wait" and t >= bot.timer:
                self._start_peek(bot)
            elif bot.state == "out" and self._walk(bot, bot.peek, dt):
                bot.state = "hold"
                bot.timer = t + (0.0 if bot.jiggle else self.rng.uniform(0.25, 1.4))
            elif bot.state == "hold" and t >= bot.timer:
                bot.state = "back"
            elif bot.state == "back" and self._walk(bot, bot.hide, dt):
                bot.state = "wait"
                bot.timer = t + self.rng.uniform(0.6, 2.5)
                self._close_event(bot, False, t)       # Bot ist entkommen

            vis = line_of_sight(self.covers, self.cam.pos, bot.pos)
            if vis and not bot.visible and bot.event is None:
                ex, ey = self.cam.angular_error_to(bot.pos)
                bot.event = {"t_vis": t, "place_err_x": round(ex, 4), "place_err_y": round(ey, 4),
                             "first_shot": None, "shots": 0, "peek_speed": bot.speed}
            bot.visible = vis

    # ---------------------------------------------------------- Schiessen
    def on_click(self, t):
        speed = self.speed
        spread = 0.0 if speed <= ACCURATE_SPEED else MAX_MOVE_SPREAD * min(1.0, speed / RUN_SPEED)
        self.moving_shots += spread > 0
        f, r, u = self.cam.basis()
        if spread:
            a = math.tan(math.radians(spread * math.sqrt(self.rng.random())))
            phi = self.rng.uniform(0, 2 * math.pi)
            d = tuple(f[i] + a * (math.cos(phi) * r[i] + math.sin(phi) * u[i]) for i in range(3))
            n = math.sqrt(sum(x * x for x in d))
            d = tuple(x / n for x in d)
        else:
            d = f
        # Schuss dem sichtbaren Bot zuordnen, der dem Fadenkreuz am naechsten ist
        open_bots = [b for b in self.targets if b.event]
        if open_bots:
            near = min(open_bots, key=lambda b: math.hypot(*self.cam.angular_error_to(b.pos)))
            near.event["shots"] += 1
            if near.event["first_shot"] is None:
                near.event["first_shot"] = round(t - near.event["t_vis"], 4)
        bot, part = self.shoot(t, d, self.covers)
        if part == "head":
            self._kill(bot, t)
            self._close_event(bot, True, t)
            self.targets.remove(bot)
            self.respawns.append(t + self.rng.uniform(1.0, 2.0))


MODES = {"flick": FlickMode, "gridshot": GridshotMode, "tracking": TrackingMode, "peek": PeekMode}
