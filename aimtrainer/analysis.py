"""Analyse-Engine & Sensitivity-Rechner.

Grundidee (Motorik-Modell nach Meyer et al., "optimized submovement model"):
Ein Flick besteht aus einer schnellen, ballistischen PRIMAERbewegung und danach
kleinen Korrekturbewegungen. Die Primaerbewegung ist der Teil, den das Gehirn
"blind" aus dem Muskelgedaechtnis plant - und genau sie verraet, ob deine
Sensitivity zu deiner Handkalibrierung passt:

    gain = zurueckgelegter Winkel am Ende der Primaerbewegung / Winkel zum Ziel

    gain > 1  -> Overshoot  (Hand plant Weg X, Sens macht daraus zu viel Winkel)
    gain < 1  -> Undershoot

Weil Winkel = Handweg * Sens * k gilt, ist die Korrektur multiplikativ:

    sens_neu = sens_alt * gain_ziel / gain_gemessen

gain_ziel ist standardmaessig 0.97: Menschen landen bei schnellen Zielbewegungen
natuerlich minimal VOR dem Ziel (kostet weniger Zeit als Zurueckkorrigieren).
Alles wird im Log-Raum robust gemittelt (Median, MAD-Ausreisserfilter, Bootstrap-
Konfidenzintervall), mit Tracking-Daten kombiniert, nach Datenmenge gedaempft und
auf max. +-10 % pro Session begrenzt.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from .valorant_math import cm_per_360


@dataclass
class AnalysisConfig:
    gain_target: float = 0.97      # gewuenschter Primaer-Gain
    min_flick_deg: float = 3.0     # kleinere Flicks sind reine Mikrokorrektur
    end_vel_frac: float = 0.08     # Primaerbewegung endet bei v < 8 % v_peak
    onset_vel_frac: float = 0.10
    min_peak_vel: float = 40.0     # Grad/s
    rt_range: tuple = (0.10, 1.0)  # plausible Reaktionszeiten [s]
    gain_range: tuple = (0.35, 2.2)
    flick_weight: float = 0.7      # Anteil Flick vs. Tracking an der Empfehlung
    shrink_k: float = 15.0         # Daempfung: n / (n + k)
    max_step: float = 0.10         # max. +-10 % Aenderung pro Session
    dead_zone: float = 0.015       # < 1.5 % Abweichung = im Rauschen
    bootstrap: int = 1000


@dataclass
class FlickMetrics:
    distance_deg: float
    direction: int                 # +1 rechts, -1 links
    reaction_time: float
    peak_velocity: float
    primary_gain: float
    primary_end_time: float
    max_overshoot_deg: float       # wie weit maximal ueber das Ziel hinaus
    lateral_error_deg: float       # seitliche Abweichung am Primaer-Ende
    corrections: int
    time_to_kill: float | None
    hit: bool
    click_speed: float | None      # Fadenkreuz-Geschwindigkeit beim Kill-Klick [Grad/s]
    dwell_before_click: float | None   # Zeit auf dem Ziel bis zum Klick
    miss_clicks_short: int         # Fehlklicks vor dem Ziel (zu frueh)
    miss_clicks_long: int          # Fehlklicks hinter dem Ziel (zu weit)

    @property
    def kind(self):
        return "overshoot" if self.primary_gain > 1.0 else "undershoot"


@dataclass
class TrackingMetrics:
    on_target_pct: float
    velocity_gain: float           # Fadenkreuz- / Zielgeschwindigkeit in Strafe-Phasen
    mean_lag_deg: float            # + = hinter dem Ziel, - = vor dem Ziel
    mean_lag_ms: float
    jitter_deg: float              # hochfrequentes Zittern (RMS)
    reversal_reaction_ms: float    # Reaktion auf Richtungswechsel
    samples: int


@dataclass
class Recommendation:
    current_sens: float
    recommended_sens: float
    factor: float
    raw_factor: float
    confidence: float
    flick_gain: float | None
    flick_gain_ci: tuple | None
    tracking_gain: float | None
    n_flicks: int
    verdict: str
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Signalverarbeitung
# ---------------------------------------------------------------------------
def _resample(t, *series, dt=0.001):
    """Raw-Input-Events kommen in unregelmaessigen Abstaenden -> 1 kHz-Raster."""
    t = np.asarray(t, float)
    grid = np.arange(t[0], t[-1] + dt * 0.5, dt)
    return (grid,) + tuple(np.interp(grid, t, np.asarray(s, float)) for s in series)


def _smooth(x, win):
    if win <= 1 or len(x) < win:
        return x
    k = np.ones(win) / win
    # zweimal Box-Filter = Dreiecksfilter, ohne Phasenverschiebung (mode='same')
    pad = win
    xp = np.concatenate([np.full(pad, x[0]), x, np.full(pad, x[-1])])
    y = np.convolve(np.convolve(xp, k, "same"), k, "same")
    return y[pad:-pad]


# ---------------------------------------------------------------------------
# Flick-Analyse
# ---------------------------------------------------------------------------
def analyze_flick(trial: dict, cfg: AnalysisConfig = AnalysisConfig()) -> FlickMetrics | None:
    s = np.asarray(trial["samples"], float)
    if len(s) < 3:
        return None
    # Ziel steht still; Fehler e(t) = Ziel - Fadenkreuz. Ab dem letzten Klick egal.
    t_end = trial["clicks"][-1][0] if trial["clicks"] else s[-1, 0]
    t_end = max(t_end, s[0, 0] + 0.01)
    ex0, ey0 = s[0, 1], s[0, 2]
    D = math.hypot(ex0, ey0)
    r_ang = trial["target_radius_deg"]
    if D < max(cfg.min_flick_deg, 3 * r_ang):
        return None

    # Bewegung bis kurz nach dem Kill-Klick beruecksichtigen
    s = np.vstack([s, [t_end + 0.05, s[-1, 1], s[-1, 2]]]) if s[-1, 0] < t_end + 0.05 else s
    t, ex, ey = _resample(s[:, 0], s[:, 1], s[:, 2])
    ux, uy = ex0 / D, ey0 / D
    px, py = ex0 - ex, ey0 - ey                 # Fadenkreuz-Weg seit Spawn
    prog = px * ux + py * uy                    # entlang Ziel-Richtung
    perp = -px * uy + py * ux                   # seitlich
    vel = _smooth(np.gradient(prog, t), 9)

    vmax_i = int(np.argmax(vel))
    vmax = vel[vmax_i]
    if vmax < cfg.min_peak_vel:
        return None
    above = np.nonzero(vel[: vmax_i + 1] < cfg.onset_vel_frac * vmax)[0]
    onset_i = int(above[-1]) + 1 if len(above) else 0
    rt = t[onset_i]

    after = np.nonzero(vel[vmax_i:] < cfg.end_vel_frac * vmax)[0]
    end_i = vmax_i + int(after[0]) if len(after) else len(vel) - 1
    gain = prog[end_i] / D

    if not (cfg.rt_range[0] <= rt <= cfg.rt_range[1] and cfg.gain_range[0] <= gain <= cfg.gain_range[1]):
        return None

    upto = np.searchsorted(t, t_end) + 1
    max_over = float(np.max(prog[onset_i:upto]) - D)

    # Korrekturbewegungen = weitere Geschwindigkeits-Peaks (beide Richtungen)
    speed = np.abs(vel[end_i:upto])
    thr = 0.15 * vmax
    corrections = 0
    if len(speed) > 2:
        peaks = (speed[1:-1] > speed[:-2]) & (speed[1:-1] >= speed[2:]) & (speed[1:-1] > thr)
        corrections = int(np.count_nonzero(peaks))

    # Klick-Timing
    dist = np.hypot(ex, ey)
    vel2d = _smooth(np.hypot(np.gradient(px, t), np.gradient(py, t)), 9)
    hit = trial["result"] == "hit"
    click_speed = dwell = ttk = None
    short = long_ = 0
    for ct, was_hit in trial["clicks"]:
        i = min(int(np.searchsorted(t, ct)), len(t) - 1)
        if was_hit:
            ttk, click_speed = ct, float(vel2d[i])
            outside = np.nonzero(dist[: i + 1] > r_ang)[0]
            if not len(outside):
                dwell = float(ct - t[0])
            else:
                dwell = 0.0 if outside[-1] >= i else float(ct - t[outside[-1] + 1])
        elif prog[i] < D:
            short += 1
        else:
            long_ += 1

    return FlickMetrics(
        distance_deg=D, direction=1 if ex0 > 0 else -1, reaction_time=float(rt),
        peak_velocity=float(vmax), primary_gain=float(gain), primary_end_time=float(t[end_i] - rt),
        max_overshoot_deg=max_over, lateral_error_deg=float(perp[end_i]), corrections=corrections,
        time_to_kill=ttk, hit=hit, click_speed=click_speed, dwell_before_click=dwell,
        miss_clicks_short=short, miss_clicks_long=long_)


# ---------------------------------------------------------------------------
# Tracking-Analyse
# ---------------------------------------------------------------------------
def analyze_tracking(samples, settle=0.15) -> TrackingMetrics | None:
    a = np.asarray(samples, float)
    if len(a) < 200:
        return None
    t, ex, ey, ty, on = _resample(a[:, 0], a[:, 1], a[:, 2], np.unwrap(np.radians(a[:, 3])), a[:, 4])
    ty = np.degrees(ty)
    vt = _smooth(np.gradient(ty, t), 15)                    # Ziel-Winkelgeschwindigkeit
    vc = vt - _smooth(np.gradient(ex, t), 15)               # Fadenkreuz = Ziel - d(Fehler)/dt
    vmax = np.percentile(np.abs(vt), 95)
    if vmax < 1.0:
        return None

    moving = np.abs(vt) > 0.5 * vmax
    sign = np.sign(vt)
    # Richtungswechsel finden, danach 'settle' Sekunden ignorieren (Reaktionsphase)
    rev = np.nonzero(np.diff(sign[moving]) != 0)[0]
    idx_moving = np.nonzero(moving)[0]
    steady = moving.copy()
    n_settle = int(settle / (t[1] - t[0]))
    rev_idx = idx_moving[rev + 1] if len(rev) else np.array([], int)
    for i in rev_idx:
        steady[i: i + n_settle] = False
    if steady.sum() < 100:
        steady = moving

    vel_gain = float(np.sum(vc[steady] * sign[steady]) / np.sum(np.abs(vt[steady])))
    lag = ex[steady] * sign[steady]
    mean_lag = float(np.mean(lag))
    lag_ms = float(np.mean(lag / np.abs(vt[steady])) * 1000)
    jitter = float(np.sqrt(np.mean((ex - _smooth(ex, 101)) ** 2)))

    # Reaktion auf Richtungswechsel: bis Fadenkreuz-Velocity das Vorzeichen wechselt
    reacts = []
    for i in rev_idx:
        new = sign[i]
        j = np.nonzero(vc[i: i + 600] * new > 0.3 * vmax)[0]
        if len(j):
            reacts.append(j[0])
    react_ms = float(np.median(reacts)) if reacts else float("nan")

    return TrackingMetrics(on_target_pct=float(np.mean(on > 0.5) * 100), velocity_gain=vel_gain,
                           mean_lag_deg=mean_lag, mean_lag_ms=lag_ms, jitter_deg=jitter,
                           reversal_reaction_ms=react_ms, samples=len(a))


# ---------------------------------------------------------------------------
# Sensitivity-Empfehlung
# ---------------------------------------------------------------------------
def _robust_log_gains(flicks):
    lg = np.log([f.primary_gain for f in flicks])
    med = np.median(lg)
    mad = np.median(np.abs(lg - med)) * 1.4826 or 1e-9
    keep = np.abs(lg - med) <= 3 * mad
    return lg[keep], [f for f, k in zip(flicks, keep) if k]


def recommend(sens, flicks, tracking=None, cfg: AnalysisConfig = AnalysisConfig(), seed=0) -> Recommendation:
    notes = []
    log_f, flick_gain, ci, n = 0.0, None, None, 0
    have_flick = len(flicks) >= 5
    if have_flick:
        lg, kept = _robust_log_gains(flicks)
        n = len(lg)
        med = float(np.median(lg))
        rng = np.random.default_rng(seed)
        boots = np.median(rng.choice(lg, (cfg.bootstrap, n)), axis=1)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        flick_gain, ci = math.exp(med), (math.exp(lo), math.exp(hi))
        flick_log_f = math.log(cfg.gain_target) - med

        # Range-Effekt: kurze Flicks overshooten, lange undershooten -> Motorik, nicht Sens
        d = np.log([f.distance_deg for f in kept])
        if n >= 10 and np.ptp(d) > 0.5:
            slope = float(np.polyfit(d, lg, 1)[0])
            if slope < -0.08:
                notes.append(f"Range-Effekt erkannt (Steigung {slope:+.2f}): kurze Flicks zu weit, lange zu kurz. "
                             "Das ist Motorik/Training, kein Sens-Problem – trainiere gemischte Distanzen.")
        # Links/Rechts-Asymmetrie (Handgelenk vs. Arm)
        L = [math.log(f.primary_gain) for f in kept if f.direction < 0]
        R = [math.log(f.primary_gain) for f in kept if f.direction > 0]
        if len(L) >= 4 and len(R) >= 4:
            gl, gr = math.exp(np.median(L)), math.exp(np.median(R))
            if abs(math.log(gl / gr)) > 0.06:
                notes.append(f"Asymmetrie: links Gain {gl:.2f}, rechts {gr:.2f}. Das kann keine Sens beheben – "
                             "prüfe Mauspad- und Armposition.")
    else:
        flick_log_f = 0.0
        notes.append("Zu wenige gültige Flicks (< 5) für eine Flick-basierte Empfehlung.")

    tracking_gain = None
    if tracking is not None and (tracking.on_target_pct < 15.0 or not 0.6 <= tracking.velocity_gain <= 1.6):
        notes.append(f"Tracking zählt nicht für die Sens: nur {tracking.on_target_pct:.0f} % der Zeit auf dem Ziel "
                     "(mindestens 15 % nötig). Versuche, dem Kopf durchgehend zu folgen.")
    elif tracking is not None and math.isfinite(tracking.velocity_gain):
        tracking_gain = tracking.velocity_gain
        track_log_f = -math.log(tracking_gain)
        if tracking.jitter_deg > 0.12:
            notes.append(f"Hohes Zittern beim Tracking ({tracking.jitter_deg:.2f}° RMS) – Hinweis auf zu hohe Sens "
                         "oder einen verkrampften Griff.")
    else:
        track_log_f = 0.0

    if have_flick and tracking_gain:
        log_f = cfg.flick_weight * flick_log_f + (1 - cfg.flick_weight) * track_log_f
    elif have_flick:
        log_f = flick_log_f
    elif tracking_gain:
        log_f = track_log_f

    n_eff = n + (40 if tracking_gain else 0) * (1 - cfg.flick_weight if have_flick else 1)
    shrink = n_eff / (n_eff + cfg.shrink_k)
    # breites Konfidenzintervall -> weniger Vertrauen
    if ci:
        width = math.log(ci[1] / ci[0])
        shrink *= max(0.25, min(1.0, 1.0 - (width - 0.05) / 0.3))
    raw_factor = math.exp(log_f)
    factor = math.exp(max(-cfg.max_step, min(cfg.max_step, log_f * shrink)))

    if abs(factor - 1) < cfg.dead_zone:
        verdict = "Deine Sensitivity passt. Die Abweichung liegt im Messrauschen – nicht ändern."
        factor = 1.0
    elif factor < 1:
        verdict = f"Du ziehst systematisch zu weit (Overshoot) – Sens um {(1 - factor) * 100:.1f} % senken."
    else:
        verdict = f"Du stoppst systematisch zu früh (Undershoot) – Sens um {(factor - 1) * 100:.1f} % erhöhen."

    return Recommendation(current_sens=sens, recommended_sens=round(sens * factor, 3), factor=factor,
                          raw_factor=raw_factor, confidence=shrink, flick_gain=flick_gain, flick_gain_ci=ci,
                          tracking_gain=tracking_gain, n_flicks=n, verdict=verdict, notes=notes)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def analyze_session(session: dict, cfg: AnalysisConfig = AnalysisConfig()):
    flicks = [m for tr in session.get("trials", []) if (m := analyze_flick(tr, cfg))]
    tracking = analyze_tracking(session["tracking"]) if session.get("tracking") else None
    rec = recommend(session["settings"]["sens"], flicks, tracking, cfg)
    return flicks, tracking, rec


MODE_NAMES = {"flick": "Flick", "gridshot": "Multi-Bot", "tracking": "Tracking", "peek": "Peek (Bewegung)"}


def _peek_report(session) -> list[str]:
    """Peek-Modus: Reaktion auf auftauchende Bots, Crosshair-Placement, Schiessen in Bewegung."""
    peeks = session.get("peeks") or []
    shots, kills, moving = session.get("shots", 0), session.get("kills", 0), session.get("moving_shots", 0)
    L = ["", f"-- Peeks ({len(peeks)} gesehen) --"]
    if not peeks:
        return L + ["Keine Peeks gesehen – lauf näher an die Kisten heran."]
    killed = [p for p in peeks if p["killed"]]
    L.append(f"Erwischt: {len(killed)}   Entkommen: {len(peeks) - len(killed)}   "
             f"({len(killed) / len(peeks) * 100:.0f} % der Peeks bestraft)")
    if killed:
        L.append(f"Zeit vom Auftauchen bis zum Kill (Median): "
                 f"{np.median([p['reaction'] for p in killed]) * 1000:.0f} ms")
    first = [p["first_shot"] for p in peeks if p["first_shot"] is not None]
    if first:
        L.append(f"Zeit bis zum ersten Schuss (Median): {np.median(first) * 1000:.0f} ms")
    ex = float(np.median([abs(p["place_err_x"]) for p in peeks]))
    ey = float(np.median([abs(p["place_err_y"]) for p in peeks]))
    L.append(f"Fadenkreuz beim Auftauchen daneben: {ey:.2f}° vertikal, {ex:.1f}° horizontal")
    if ey > 1.0:
        L.append("  -> Halte das Fadenkreuz konsequent auf Kopfhöhe (Horizontlinie).")
    if ex > 10:
        L.append("  -> Halte das Fadenkreuz näher an den Kanten, an denen ein Bot auftauchen kann.")
    if shots:
        L.append(f"Headshot-Quote: {kills / shots * 100:.0f} %   Schüsse in Bewegung: {moving} von {shots} "
                 f"({moving / shots * 100:.0f} %)")
        if moving / shots > 0.2:
            L.append("  -> Zu viele Schüsse in Bewegung. Erst stoppen (Counter-Strafe), dann schießen.")
    return L


def build_report(session, flicks, tracking, rec) -> list[str]:
    """Report als Zeilen. Markierungen fuer die Darstellung: '-- Titel --' = Abschnitt,
    '>>> ' = Hauptergebnis, '  -> ' = Tipp, '* ' = Hinweis, '' = Abschnittsende."""
    st = session["settings"]
    dpi = st["dpi"]
    trials = session.get("trials", [])
    L = ["=== AIM-ANALYSE ===",
         f"Modus: {MODE_NAMES.get(st['mode'], st['mode'])}   |   Sens {st['sens']} bei {dpi:.0f} DPI   |   "
         f"eDPI {st['sens'] * dpi:.0f}   |   {cm_per_360(st['sens'], dpi):.1f} cm/360°"]
    if trials:
        hits = sum(t["result"] == "hit" for t in trials)
        shots = sum(len(t["clicks"]) for t in trials)
        L.append(f"Ziele: {len(trials)}   Kills: {hits}   Schüsse: {shots}   "
                 f"Genauigkeit: {hits / shots * 100 if shots else 0:.1f} %")
    if flicks:
        g = np.array([f.primary_gain for f in flicks])
        over = np.mean(g > 1.0) * 100
        L += ["", f"-- Flicks ({len(flicks)} gültig) --",
              f"Reaktionszeit (Median): {np.median([f.reaction_time for f in flicks]) * 1000:.0f} ms",
              f"Primär-Gain (Median): {np.median(g):.3f}   (1,000 = genau aufs Ziel)",
              f"Zu weit (Overshoot): {over:.0f} %   Zu kurz (Undershoot): {100 - over:.0f} %",
              f"Mittlerer Overshoot: {np.mean([max(0, f.max_overshoot_deg) for f in flicks]):.2f}°",
              f"Korrekturen pro Flick: {np.mean([f.corrections for f in flicks]):.2f}",
              f"Seitlicher Fehler: {np.mean(np.abs([f.lateral_error_deg for f in flicks])):.2f}°"]
        ttk = [f.time_to_kill for f in flicks if f.time_to_kill]
        if ttk:
            L.append(f"Zeit bis zum Kill (Median): {np.median(ttk) * 1000:.0f} ms")
        cs = [f.click_speed for f in flicks if f.click_speed is not None]
        dw = [f.dwell_before_click for f in flicks if f.dwell_before_click is not None]
        if cs:
            L.append(f"Klick-Timing: {np.median(dw) * 1000:.0f} ms auf dem Ziel vor dem Schuss, "
                     f"Fadenkreuz-Tempo beim Kill {np.median(cs):.0f}°/s")
            if np.median(dw) > 0.12:
                L.append("  -> Du zögerst auf dem Ziel. Vertraue dem Flick und klicke früher.")
        sh = sum(f.miss_clicks_short for f in flicks)
        lo = sum(f.miss_clicks_long for f in flicks)
        if sh + lo:
            L.append(f"Fehlklicks: {sh} zu früh (vor dem Ziel), {lo} zu weit (hinter dem Ziel)")
    if tracking:
        L += ["", "-- Tracking --",
              f"Auf dem Ziel: {tracking.on_target_pct:.1f} % der Zeit",
              f"Geschwindigkeits-Gain: {tracking.velocity_gain:.3f}   (1,000 = perfekt mitgezogen)",
              f"Verzögerung: {tracking.mean_lag_deg:+.2f}° ({tracking.mean_lag_ms:+.0f} ms)   (+ = hinterher)",
              f"Zittern: {tracking.jitter_deg:.3f}° RMS",
              f"Reaktion auf Richtungswechsel: {tracking.reversal_reaction_ms:.0f} ms"]
    if st["mode"] == "peek":
        L += _peek_report(session)
        L += ["", "-- Hinweis --",
              "Die Sens-Empfehlung kommt aus Flick, Multi-Bot und Tracking. Im Peek-Modus verfälschen "
              "deine eigene Bewegung und laufende Bots die Over-/Undershoot-Messung."]
        return L
    L += ["", "-- Sensitivity-Empfehlung --", rec.verdict]
    if rec.flick_gain_ci:
        L.append(f"Flick-Gain {rec.flick_gain:.3f}   (95 %-Bereich {rec.flick_gain_ci[0]:.3f} – "
                 f"{rec.flick_gain_ci[1]:.3f})")
    L.append(f"Rohfaktor {rec.raw_factor:.3f}   |   Vertrauen {rec.confidence * 100:.0f} %   |   "
             f"angewandt {rec.factor:.3f}")
    L.append(f">>> Perfekte Valorant-Sens: {rec.recommended_sens:.3f}   "
             f"({cm_per_360(rec.recommended_sens, dpi):.1f} cm/360°, eDPI {rec.recommended_sens * dpi:.0f})")
    L += [f"* {n}" for n in rec.notes]
    return L
