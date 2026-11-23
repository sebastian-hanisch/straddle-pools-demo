"""Wiederholbarkeit der parallelen Verfahren: P0 und P1 mit drei verschiedenen Zufallswerten des Lösers (CP-SAT, ein Prozess), sonst gleiche Eingabe.

Aufruf (aus dem Repo-Ordner):  python tools/wiederholbarkeit.py [--out data/wiederholbarkeit.json]
Auch wenn jedes Pool-Modell bewiesen optimal ist, kann es mehrere gleich gute Pläne geben; die Neuberechnung mit allen Abhängigkeiten bewertet sie verschieden.
Verglichen werden die Zielwerte von P0 und P1 je Zufallswert des Lösers mit dem gespeicherten Wert der Gesamtplanung mit festen Pools (data/messreihe.json)."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import stp_constants as C  # noqa: E402
import stp_evaluation as ev  # noqa: E402
import stp_heuristic as H  # noqa: E402
import stp_instance as I  # noqa: E402
import stp_parallel as PA  # noqa: E402
import stp_pools as PL  # noqa: E402
import stp_timing as M  # noqa: E402

SCENARIOS = ("Kleiner Hafen", "Schlechte Stapelung")
SOLVER_SEEDS = (1, 2, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "wiederholbarkeit.json"))
    args = ap.parse_args()
    series = ev.load_series()
    out = {"meta": {"date": date.today().strftime("%d.%m.%Y"), "solver_seeds": list(SOLVER_SEEDS), "time_limit": C.TIME_LIMIT_DEFAULT, "workers": 1}, "scenarios": {}}
    for name in SCENARIOS:
        preset = C.PRESETS[name]
        recs = []
        for rec in series["scenarios"][name]["records"]:
            s = ev.Settings(**{**preset, "seed": rec["seed"]})
            inst = I.make_instance(s.seed, s.n_cranes, s.orders_per_crane, C.N_BLOCKS, s.dep_pct, s.mis_pct)
            pools = PL.make_pools(inst, s.n_sc, s.strategy)
            tk, ty = M.richtzeiten(inst)
            sp = PL.start_positions(inst, pools)
            w = dict(w_crane=s.w_crane, w_yard=C.W_YARD, penalty=s.penalty)
            hint = H.greedy_plan(inst, pools, sp, tk, ty, "fest", **w)
            row = {"seed": rec["seed"], "g2": rec["g2"], "g2_proven": rec["proven"]["g2"], "p0": [], "p1": [], "pools_proven": []}
            for solver_seed in SOLVER_SEEDS:
                stages = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=C.TIME_LIMIT_DEFAULT, workers=1, seed=solver_seed, rounds=1, **w)
                row["p0"].append(stages[0].cost.obj)
                row["p1"].append(stages[1].cost.obj)
                row["pools_proven"].append(bool(stages[0].proven and stages[1].proven))
            recs.append(row)
            print(name, rec["seed"], row["p0"], row["p1"], flush=True)
        out["scenarios"][name] = {"records": recs}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fertig:", args.out)


if __name__ == "__main__":
    main()
