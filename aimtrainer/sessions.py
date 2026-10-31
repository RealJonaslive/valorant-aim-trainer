"""Gespeicherte Runden (Ordner sessions/) auflisten, einzeln und gesamt auswerten.

Jede Runde liegt als <Datum>_<Uhrzeit>_<Modus>.json im Ordner. Fuer die Liste im
Programm wird jede Datei einmal analysiert; das Ergebnis wird im Speicher gecacht
(Schluessel: Pfad + Aenderungszeit), damit die Liste schnell bleibt.

Gesamtbilanz: Runden mit unterschiedlicher Sens sind nicht direkt vergleichbar.
Deshalb rechnet jeder gueltige Flick in eine "implizite Sens" um:

    implizite Sens = Sens der Runde * Ziel-Gain / gemessener Primaer-Gain

(= die Sens, bei der genau dieser Flick perfekt gelandet waere). Alle Flicks aller
Runden werden im Log-Raum robust gemittelt (gewichteter Median, Ausreisserfilter,
Bootstrap-Bereich). Neuere Runden zaehlen staerker (Halbwertszeit 14 Tage), weil
sich die Motorik mit der Zeit anpasst. Tracking-Runden fliessen mit 30 % ein.
"""
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np

from .analysis import MODE_NAMES, AnalysisConfig, analyze_session, build_report
from .valorant_math import cm_per_360

HALF_LIFE_DAYS = 14.0
TRACKING_MIN_ON_TARGET = 15.0   # % - darunter wurde nicht ernsthaft getrackt
_cache = {}


class SessionInfo:
    def __init__(self, path, data, report, rec, flicks, tracking):
        st = data["settings"]
        self.path = Path(path)
        self.mode = st["mode"]
        self.mode_name = MODE_NAMES.get(self.mode, self.mode)
        self.sens, self.dpi = st["sens"], st["dpi"]
        try:
            self.when = datetime.fromisoformat(data.get("started", ""))
        except ValueError:
            self.when = datetime.fromtimestamp(self.path.stat().st_mtime)
        self.report = report
        self.rec = rec if self.mode != "peek" else None
        self.flicks, self.tracking = flicks, tracking
        trials = data.get("trials", [])
        self.kills = data.get("kills", sum(t["result"] == "hit" for t in trials))
        self.shots = data.get("shots", sum(len(t["clicks"]) for t in trials))
        self.peeks = data.get("peeks", [])
        self.moving_shots = data.get("moving_shots", 0)

    @property
    def title(self):
        return f"{self.when:%d.%m.%Y   %H:%M}   ·   {self.mode_name}"

    @property
    def info_line(self):
        return f"Datei: sessions/{self.path.name}"

    @property
    def subtitle(self):
        if self.rec is None:
            return f"Sens {self.sens:.3f}   ·   {self.kills} Kills   ·   keine Sens-Empfehlung (Peek)"
        return f"Sens {self.sens:.3f}  →  Empfehlung {self.rec.recommended_sens:.3f}   ·   {self.kills} Kills"


def load(path):
    path = Path(path)
    key = (str(path), path.stat().st_mtime)
    if key not in _cache:
        data = json.loads(path.read_text("utf-8"))
        flicks, tracking, rec = analyze_session(data)
        report = build_report(data, flicks, tracking, rec)
        if "body_hits" in data:
            report.insert(2, f"Körpertreffer (kein Kill): {data['body_hits']}")
        _cache[key] = SessionInfo(path, data, report, rec, flicks, tracking)
    return _cache[key]


def list_sessions(folder):
    """Alle Runden, neueste zuerst. Kaputte Dateien werden übersprungen."""
    out = []
    for p in sorted(Path(folder).glob("*.json"), reverse=True):
        try:
            out.append(load(p))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    out.sort(key=lambda s: s.when, reverse=True)
    return out


# ---------------------------------------------------------------------------
# Gesamtbilanz
# ---------------------------------------------------------------------------
class _Rec:
    def __init__(self, recommended_sens):
        self.recommended_sens = recommended_sens


class Overall:
    """Sieht für die Oberfläche aus wie eine Runde (title, report, rec), plus Verlauf."""
    path = None

    def __init__(self, title, info_line, report, rec, series, current, target):
        self.title, self.info_line, self.report, self.rec = title, info_line, report, rec
        self.series, self.current, self.target = series, current, target


def tracking_usable(tr):
    """Tracking zählt für die Sens nur, wenn wirklich mitgezogen wurde."""
    return (tr is not None and tr.on_target_pct >= TRACKING_MIN_ON_TARGET
            and 0.6 <= tr.velocity_gain <= 1.6)


def _weighted_median(values, weights):
    order = np.argsort(values)
    v, w = np.asarray(values)[order], np.asarray(weights)[order]
    c = np.cumsum(w)
    return float(v[np.searchsorted(c, c[-1] / 2)])


def overall(history, current_sens, dpi, cfg: AnalysisConfig = AnalysisConfig(), seed=0):
    """Gesamtbilanz aus allen Runden + Empfehlung relativ zur aktuell eingestellten Sens."""
    if not history:
        return None
    now = max(s.when for s in history)
    rounds = sorted(history, key=lambda s: s.when)
    counts = {}
    for s in rounds:
        counts[s.mode_name] = counts.get(s.mode_name, 0) + 1

    # --- implizite Sens je Flick / je Tracking-Runde ---
    f_vals, f_w, t_vals, t_w, series = [], [], [], [], []
    for s in rounds:
        w = 0.5 ** ((now - s.when).total_seconds() / 86400 / HALF_LIFE_DAYS)
        vals = [math.log(s.sens * cfg.gain_target / f.primary_gain) for f in s.flicks]
        f_vals += vals
        f_w += [w] * len(vals)
        track_ok = tracking_usable(s.tracking)
        if track_ok:
            t_vals.append(math.log(s.sens / s.tracking.velocity_gain))
            t_w.append(w)
        point = None
        if len(vals) >= 5:
            point = math.exp(float(np.median(vals)))
        elif track_ok:
            point = s.sens / s.tracking.velocity_gain
        if point:
            series.append((s.when, point, s.sens))

    head = [f"Runden: {len(rounds)}   ("
            + ", ".join(f"{n}× {m}" for m, n in counts.items()) + ")",
            f"Zeitraum: {rounds[0].when:%d.%m.%Y} – {rounds[-1].when:%d.%m.%Y}   ·   "
            f"aktuell eingestellt: Sens {current_sens:.3f} bei {dpi:.0f} DPI"]
    kills, shots = sum(s.kills for s in rounds), sum(s.shots for s in rounds)
    if shots:
        head.append(f"Kills gesamt: {kills}   ·   Schüsse gesamt: {shots}   ·   Trefferquote: "
                    f"{kills / shots * 100:.1f} %")
    lines = ["=== GESAMTBILANZ ==="] + head

    # --- Empfehlung ---
    notes, target, rec = [], None, None
    n_f = len(f_vals)
    if n_f >= 5:
        v, w = np.array(f_vals), np.array(f_w)
        med = np.median(v)
        mad = np.median(np.abs(v - med)) * 1.4826 or 1e-9
        keep = np.abs(v - med) <= 3 * mad
        v, w = v[keep], w[keep]
        center = _weighted_median(v, w)
        rng = np.random.default_rng(seed)
        p = w / w.sum()
        boots = [_weighted_median(rng.choice(v, len(v), p=p), np.ones(len(v))) for _ in range(400)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        n_eff = float(w.sum())
        if t_vals:
            # Gewicht nach Datenmenge: eine Tracking-Runde ~ 20 Flicks, Tracking-Anteil max. 30 %
            wf, wt = n_eff, 20.0 * float(np.sum(t_w))
            share = min(1 - cfg.flick_weight, wt / (wf + wt))
            center = (1 - share) * center + share * float(np.average(t_vals, weights=t_w))
            n_eff += wt * share
        ci = (math.exp(lo), math.exp(hi))
    elif t_vals:
        center, ci = float(np.average(t_vals, weights=t_w)), None
        n_eff = 20.0 * len(t_vals)
    else:
        center = None

    lines += ["", "-- Sens-Empfehlung aus allen Runden --"]
    if center is None:
        lines += ["Noch zu wenig Daten. Spiel ein paar Runden Flick, Multi-Bot oder Tracking – "
                  "Peek-Runden zählen für die Sens nicht."]
    else:
        target = math.exp(center)
        shrink = n_eff / (n_eff + cfg.shrink_k)
        step = max(-cfg.max_step, min(cfg.max_step, (center - math.log(current_sens)) * shrink))
        factor = math.exp(step)
        if abs(factor - 1) < cfg.dead_zone:
            factor, verdict = 1.0, "Deine aktuelle Sens passt – über alle Runden gesehen. Nicht ändern."
        elif factor < 1:
            verdict = (f"Über alle Runden ziehst du eher zu weit. Senke die Sens um "
                       f"{(1 - factor) * 100:.1f} % (in kleinen Schritten).")
        else:
            verdict = (f"Über alle Runden stoppst du eher zu früh. Erhöhe die Sens um "
                       f"{(factor - 1) * 100:.1f} % (in kleinen Schritten).")
        recommended = round(current_sens * factor, 3)
        rec = _Rec(recommended)
        lines.append(verdict)
        lines.append(f"Ausgewertet: {n_f} gültige Flicks"
                     + (f" und {len(t_vals)} Tracking-Runde(n)" if t_vals else ""))
        rng_txt = f"   (95 %-Bereich {ci[0]:.3f} – {ci[1]:.3f})" if ci else ""
        lines.append(f"Langfristiger Zielwert: {target:.3f}{rng_txt}")
        lines.append(f"Vertrauen: {shrink * 100:.0f} %   ·   max. 10 % Änderung pro Schritt")
        lines.append(f">>> Empfohlene Valorant-Sens: {recommended:.3f}   "
                     f"({cm_per_360(recommended, dpi):.1f} cm/360°, eDPI {recommended * dpi:.0f})")
        notes.append("Neuere Runden zählen stärker als alte (Halbwertszeit 14 Tage).")
        if ci and math.log(ci[1] / ci[0]) > 0.15:
            notes.append("Der Bereich ist noch breit – mehr Flick-Runden machen die Empfehlung genauer.")
        if abs(math.log(target / current_sens)) > 0.1:
            notes.append("Zielwert und aktuelle Sens liegen weit auseinander. Geh lieber in mehreren "
                         "Schritten dorthin und spiel nach jeder Änderung ein paar Runden.")
        lines += [f"* {n}" for n in notes]

    # --- Entwicklung (erste vs. letzte Flick-Runden) ---
    fr = [s for s in rounds if len(s.flicks) >= 5]
    if len(fr) >= 2:
        k = max(1, len(fr) // 3)
        first, last = fr[:k], fr[-k:]

        def med(rs, fn):
            return float(np.median([fn(f) for s in rs for f in s.flicks]))

        def acc(rs):
            sh = sum(s.shots for s in rs)
            return sum(s.kills for s in rs) / sh * 100 if sh else 0.0
        lines += ["", "-- Deine Entwicklung (Flick/Multi-Bot) --",
                  f"Reaktionszeit: {med(first, lambda f: f.reaction_time) * 1000:.0f} ms → "
                  f"{med(last, lambda f: f.reaction_time) * 1000:.0f} ms",
                  f"Trefferquote: {acc(first):.0f} % → {acc(last):.0f} %",
                  f"Korrekturen pro Flick (Schnitt): "
                  f"{np.mean([f.corrections for s in first for f in s.flicks]):.1f} → "
                  f"{np.mean([f.corrections for s in last for f in s.flicks]):.1f}",
                  f"(erste {k} Runde(n) verglichen mit den letzten {k})"]

    tr = [s for s in rounds if s.tracking is not None]
    if tr:
        lines += ["", "-- Tracking --",
                  f"{len(tr)} Runde(n)   ·   Auf dem Ziel im Schnitt "
                  f"{np.mean([s.tracking.on_target_pct for s in tr]):.1f} % der Zeit",
                  f"Letzte Runde: {tr[-1].tracking.on_target_pct:.1f} %"]

    pk = [s for s in rounds if s.mode == "peek"]
    if pk:
        peeks = [p for s in pk for p in s.peeks]
        killed = [p for p in peeks if p.get("killed")]
        sh, mv = sum(s.shots for s in pk), sum(s.moving_shots for s in pk)
        lines += ["", "-- Peek --", f"{len(pk)} Runde(n)   ·   {len(peeks)} Peeks gesehen, "
                  f"{len(killed)} erwischt ({len(killed) / len(peeks) * 100 if peeks else 0:.0f} %)"]
        if killed:
            lines.append(f"Zeit vom Auftauchen bis zum Kill (Median): "
                         f"{np.median([p['reaction'] for p in killed]) * 1000:.0f} ms")
        if sh:
            lines.append(f"Schüsse in Bewegung: {mv / sh * 100:.0f} %")
            if mv / sh > 0.2:
                lines.append("  -> Bleib vor dem Schießen öfter stehen (Counter-Strafe).")

    title = "Gesamtbilanz – alle Runden"
    info = f"Aus {len(rounds)} gespeicherten Runden berechnet"
    return Overall(title, info, lines, rec, series, current_sens, target)
