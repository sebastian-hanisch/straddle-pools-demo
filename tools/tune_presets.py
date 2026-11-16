"""Wählt die Zufalls-Seeds der Presets aus der vorgerechneten Messreihe (data/messreihe.json) und schreibt tools/PRESET_SWEEP.md.

Aufruf (aus dem Repo-Ordner):  python tools/tune_presets.py [--write]

Auswahl je Szenario: ein TYPISCHER Seed, dessen Verhältnisse (Gesamt fest zu ohne Pooling, mit Leihen zu ohne Pooling, Parallel + Runde zu Gesamt fest) am nächsten an den Medianen
des Szenarios liegen und dessen drei Gesamtmodelle bewiesen sind. Ausnahme „Schlechte Stapelung“: Dort ist der Median „Parallel gleich Gesamt“; das Szenario soll aber den
Fall zeigen, dass die getrennte Rechnung teuer wird. Gewählt wird deshalb unter den Instanzen mit Aufschlag (mehr als doppelt) die typischste; der Hilfetext des Presets sagt das.
Mit --write werden die gewählten Seeds in stp_constants.py (PRESETS) eingetragen."""

import argparse
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT))

import stp_constants as C  # noqa: E402
import stp_evaluation as ev  # noqa: E402

WITH_SURCHARGE = {"Schlechte Stapelung"}


def features(r):
    return (math.log((r["g2"] + 1) / (r["g1"] + 1)), math.log((r["g3"] + 1) / (r["g1"] + 1)), math.log((r["p1"] + 1) / (r["g2"] + 1)))


def pick(records, with_surcharge, robust=frozenset()):
    """Typischste Instanz: unter den Instanzen mit bewiesenen Gesamtmodellen (bei with_surcharge nur solche mit Aufschlag von Parallel + Runde) diejenige mit der kleinsten Summe der
    Abstände der drei logarithmierten Verhältnisse zu ihren Medianen; liegen Instanzen mit allen Verhältnissen höchstens um den Faktor 1,5 vom Median, wird nur unter diesen gewählt."""
    ok = [r for r in records if r["proven"]["g2"]]            # G2 bewiesen (die Aussagen über „Optimum“ der Gesamtplanung mit festen Pools); G1 und G3 nur, soweit das Zeitlimit reichte
    pool = [r for r in ok if ev.is_double(r["p1"], r["g2"]) and r["seed"] in robust] if with_surcharge else ok   # Aufschlag in allen Läufen (tools/wiederholbarkeit.py), sonst nicht zuverlässig
    if not pool:
        pool = ok
    med = [st.median(features(r)[i] for r in records) for i in range(3)]     # Median über ALLE Instanzen des Szenarios (nicht nur über die bewiesenen)
    n_feat = 2 if with_surcharge else 3                   # bei den Szenarien mit Aufschlag zählt das dritte Verhältnis (Parallel gegen Gesamt) nicht

    def dist(r):
        return sum(abs(features(r)[i] - med[i]) for i in range(n_feat))

    near = [r for r in pool if all(abs(features(r)[i] - med[i]) <= math.log(1.5) for i in range(n_feat))]
    return min(near or pool, key=dist)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    data = json.loads((ROOT / "data" / "messreihe.json").read_text(encoding="utf-8"))
    wh = json.loads((ROOT / "data" / "wiederholbarkeit.json").read_text(encoding="utf-8"))
    robust = {r["seed"] for r in wh["scenarios"]["Schlechte Stapelung"]["records"] if all(ev.is_double(p, r["g2"]) for p in r["p1"])}
    lines = ["# Preset-Abstimmung (aus `data/messreihe.json`)", "",
             f"Stand {data['meta']['date']}, je Szenario {data['meta']['instances']} erzeugte Instanzen (Seeds ab {data['meta']['seed0']}), Zeitlimit {data['meta']['time_limit']} s. "
             "Ausgewählt wird die Instanz mit bewiesener Gesamtplanung mit festen Pools (G2), deren Verhältnisse (G2/G1, G3/G1, P1/G2) am nächsten an den Medianen liegen und höchstens um den Faktor 1,5 davon abweichen, soweit es solche gibt (Ausnahme: Szenarien mit Aufschlag, siehe `tools/tune_presets.py`).", "",
             "| Szenario | Seed | Ordnung G1 ≤ G3 ≤ G2 ≤ P1 und G2 ≤ Liste in … | Median G2/G1 | Median G3/G1 | P1 = G2 in … | P1 mehr als doppelt in … |", "| --- | --- | --- | --- | --- | --- | --- |"]
    chosen = {}
    for name, sc in data["scenarios"].items():
        recs = sc["records"]
        r = pick(recs, name in WITH_SURCHARGE, robust)
        chosen[name] = r["seed"]
        order = sum(1 for x in recs if x["g1"] <= x["g3"] <= x["g2"] <= x["p1"] and x["g2"] <= x["list"])
        med21 = st.median((x["g2"] + 1) / (x["g1"] + 1) for x in recs)
        med31 = st.median((x["g3"] + 1) / (x["g1"] + 1) for x in recs)
        s = ev.series_stats(recs, "p1")
        lines.append(f"| {name} | {r['seed']} | {order} von {len(recs)} | {med21:.2f} | {med31:.2f} | {s['equal']} von {s['n']} | {s['double']} von {s['n']} |".replace(".", ","))
    lines += ["", "Hinweis: Das Verhältnis wird als (a + 1) / (b + 1) gebildet, damit ein Nenner 0 (keine Verspätung) das Verhältnis nicht undefiniert macht."]
    out = "\n".join(lines) + "\n"
    (ROOT / "tools" / "PRESET_SWEEP.md").write_text(out, encoding="utf-8")
    print(out)
    if args.write:
        path = ROOT / "stp_constants.py"
        text = path.read_text(encoding="utf-8")
        for name, seed in chosen.items():
            pat = re.compile(r'(\s+"' + re.escape(name) + r'": dict\(_BASE[^\n]*?)(, seed=\d+)?\),')
            if not pat.search(text):
                raise SystemExit(f"Preset {name} nicht gefunden")
            text = pat.sub(lambda m: m.group(1) + f", seed={seed}),", text, count=1)
        path.write_text(text, encoding="utf-8")
        print("Seeds eingetragen:", chosen)
    _ = C


if __name__ == "__main__":
    main()
