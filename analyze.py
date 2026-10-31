"""Mehrere Sessions gemeinsam auswerten (mehr Daten = verlaesslichere Empfehlung).

    python analyze.py                      # alle Sessions in sessions/
    python analyze.py sessions/2026*.json  # Auswahl

Sessions mit unterschiedlicher Sens sind nicht direkt vergleichbar. Daher liefert
jede Session eine "implizite Sens" (sens * Rohfaktor); diese werden im Log-Raum
nach Anzahl gueltiger Flicks gewichtet gemittelt.
"""
import glob
import json
import math
import sys

from aimtrainer.analysis import analyze_session, build_report
from aimtrainer.valorant_math import cm_per_360


def main(paths):
    paths = paths or sorted(glob.glob("sessions/*.json"))
    num = den = 0.0
    dpi = None
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            session = json.load(fh)
        flicks, tracking, rec = analyze_session(session)
        print(f"\n##### {p}")
        print("\n".join(build_report(session, flicks, tracking, rec)))
        weight = rec.n_flicks + (20 if rec.tracking_gain else 0)
        if weight:
            num += weight * math.log(rec.current_sens * rec.raw_factor)
            den += weight
            dpi = session["settings"]["dpi"]
    if den:
        sens = math.exp(num / den)
        print(f"\n===== GESAMT ueber {len(paths)} Sessions (Gewicht {den:.0f}) =====")
        print(f">>> Perfekte Valorant-Sens: {sens:.3f}  ({cm_per_360(sens, dpi):.1f} cm/360 @ {dpi:.0f} DPI)")


if __name__ == "__main__":
    main(sys.argv[1:])
