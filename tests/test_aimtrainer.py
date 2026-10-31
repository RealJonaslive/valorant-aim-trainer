"""Tests mit einem simulierten Spieler, der echte Maus-Counts erzeugt.

Der Bot plant Flicks mit einem bekannten Primaer-Gain (z.B. 1.10 = 10 % Overshoot)
als Minimum-Jerk-Bewegung, korrigiert dann aufs Ziel und klickt. Die Analyse muss
diesen Gain wiederfinden und die Sens in die richtige Richtung korrigieren.
Ausfuehren: python -m pytest tests  (oder: python tests/test_aimtrainer.py)
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aimtrainer.analysis import analyze_flick, analyze_session, analyze_tracking, recommend  # noqa: E402
from aimtrainer.camera import Camera  # noqa: E402
from aimtrainer.modes import FlickMode, TrackingMode  # noqa: E402
from aimtrainer.valorant_math import VALORANT_VFOV, cm_per_360, sens_from_cm_per_360  # noqa: E402

HZ = 1000  # Polling-Rate des simulierten Mauses


def min_jerk(tau):
    return 10 * tau ** 3 - 15 * tau ** 4 + 6 * tau ** 5


class Bot:
    def __init__(self, cam, mode, gain, rng):
        self.cam, self.mode, self.gain, self.rng = cam, mode, gain, rng
        self.acc = [0.0, 0.0]
        self.t = 0.0

    def move_deg(self, dyaw, dpitch):
        """Gradbewegung -> ganzzahlige Counts (wie ein echter Sensor), Rest wird mitgefuehrt."""
        k = 0.07 * self.cam.sens
        self.acc[0] += dyaw / k
        self.acc[1] += -dpitch / k
        dx, dy = int(round(self.acc[0])), int(round(self.acc[1]))
        self.acc[0] -= dx
        self.acc[1] -= dy
        if dx or dy:
            self.cam.apply_counts(dx, dy)
            self.mode.on_input(self.t)

    def step(self, n=1):
        for _ in range(n):
            self.t += 1 / HZ
            self.mode.update(self.t, 1 / HZ)

    def submove(self, ex, ey, duration):
        steps = int(duration * HZ)
        prev = 0.0
        for i in range(1, steps + 1):
            p = min_jerk(i / steps)
            self.move_deg(ex * (p - prev), ey * (p - prev))
            prev = p
            self.step()

    def flick_once(self):
        tg = self.mode.targets[0]
        self.step(int(self.rng.uniform(0.18, 0.25) * HZ))          # Reaktionszeit
        ex, ey = self.cam.angular_error_to(tg.pos)
        g = self.gain * math.exp(self.rng.gauss(0, 0.04))
        D = math.hypot(ex, ey)
        self.submove(ex * g, ey * g, 0.12 + 0.004 * D)              # Primaerbewegung
        self.step(40)
        ex, ey = self.cam.angular_error_to(tg.pos)
        self.submove(ex, ey, 0.12)                                   # Korrektur
        self.step(30)
        self.mode.on_click(self.t)


def run_flick_session(gain, n=40, sens=0.35, seed=1):
    rng = random.Random(seed)
    cam = Camera(sens)
    mode = FlickMode(cam, rng=random.Random(seed + 1))
    bot = Bot(cam, mode, gain, rng)
    while len(mode.trials) < n:
        bot.step()
        if mode.trial and mode.targets:
            bot.flick_once()
    return {"settings": {"sens": sens, "dpi": 800, "mode": "flick"}, "trials": mode.trials, "tracking": []}


def test_math():
    assert abs(cm_per_360(0.35, 800) - 46.65) < 0.05            # 360/(0.07*0.35*800)*2.54
    assert abs(sens_from_cm_per_360(cm_per_360(0.41, 1600), 1600) - 0.41) < 1e-9
    assert abs(VALORANT_VFOV - 70.53) < 0.01


def test_camera_counts_exact():
    cam = Camera(0.5)
    for _ in range(10000):
        cam.apply_counts(1, 0)
    assert abs(cam.yaw - 10000 * 0.035) < 1e-9


def test_overshoot_detected_and_sens_lowered():
    flicks, _, rec = analyze_session(run_flick_session(gain=1.12))
    assert len(flicks) >= 30
    assert 1.07 < rec.flick_gain < 1.17, rec.flick_gain
    assert rec.recommended_sens < 0.35
    assert rec.raw_factor < 0.9


def test_undershoot_detected_and_sens_raised():
    _, _, rec = analyze_session(run_flick_session(gain=0.82))
    assert 0.77 < rec.flick_gain < 0.87, rec.flick_gain
    assert rec.recommended_sens > 0.35


def test_good_sens_unchanged():
    _, _, rec = analyze_session(run_flick_session(gain=0.97))
    assert rec.recommended_sens == 0.35, (rec.recommended_sens, rec.flick_gain)


def test_step_limited():
    _, _, rec = analyze_session(run_flick_session(gain=1.6, n=60))
    assert abs(math.log(rec.factor)) <= 0.10 + 1e-9


def test_tracking_velocity_gain():
    for true_gain in (0.8, 1.0):
        cam = Camera(0.35)
        mode = TrackingMode(cam, rng=random.Random(3))
        bot = Bot(cam, mode, 1.0, random.Random(4))
        prev_ty = None
        for _ in range(15 * HZ):
            ty, _ = cam.angles_to(mode.targets[0].pos)
            if prev_ty is not None:
                ex, _ = cam.angular_error_to(mode.targets[0].pos)
                bot.move_deg((ty - prev_ty) * true_gain + ex * 0.002, 0)  # mitziehen + langsame Fehlerkorrektur
            prev_ty = ty
            bot.step()
        m = analyze_tracking(mode.tracking)
        assert abs(m.velocity_gain - true_gain) < 0.08, (true_gain, m.velocity_gain)
        r = recommend(0.35, [], m)
        assert (r.recommended_sens > 0.35) if true_gain < 0.9 else True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    s = run_flick_session(gain=1.12)
    from aimtrainer.analysis import build_report
    print("\n".join(build_report(s, *analyze_session(s))))
