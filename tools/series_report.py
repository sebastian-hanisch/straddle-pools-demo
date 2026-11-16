"""Kennzahlen der vorgerechneten Messreihe für die README (Ausgabe als Text). Aufruf: python tools/series_report.py"""
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import stp_evaluation as ev  # noqa: E402

d = ev.load_series()
print("meta", d["meta"])
for name, sc in {**d["scenarios"], **d["large"]}.items():
    r = sc["records"]
    n = len(r)
    pr = {k: sum(x["proven"][k] for x in r) for k in ("g1", "g2", "g3", "pn")}
    med = lambda f: st.median(f(x) for x in r)  # noqa: E731
    print(f"\n{name}: n={n}, bewiesen {pr}")
    print("  Mittel Zielwert:", {k: round(st.mean(x[k] for x in r)) for k in ("list", "g1", "g2", "g3", "p0", "p1", "pn")})
    print("  Median Zielwert:", {k: st.median(x[k] for x in r) for k in ("list", "g1", "g2", "g3", "p0", "p1", "pn")})
    print("  Median G2/G1 %.2f  G3/G1 %.2f  Liste/G2 %.2f" % (med(lambda x: (x["g2"] + 1) / (x["g1"] + 1)), med(lambda x: (x["g3"] + 1) / (x["g1"] + 1)), med(lambda x: (x["list"] + 1) / (x["g2"] + 1))))
    for key in ("p0", "p1", "pn"):
        s = ev.series_stats(r, key)
        print(f"  {key} gegen G2: gleich {s['equal']}, mehr als doppelt {s['double']}, größter Aufschlag {s['worst']}, Mittel {s['mean_key']:.0f} gegen {s['mean_ref']:.0f}")
    print("  Zeit (Mittel s):", {k: round(st.mean(y["wall"][k] for y in r), 1) for k in ("g1", "g2", "g3", "p0", "p1", "pn")})
    print("  poolfremd G3 Mittel %.1f, Kreuzkanten Mittel %.1f, Neu-Sequenzierung in %d" % (st.mean(x["foreign_g3"] for x in r), st.mean(x["cross_arcs"] for x in r), sum(x["reseq"] for x in r)))
