"""Vorgerechnete Messreihe: je Preset-Szenario viele erzeugte Instanzen, dazu wenige große Instanzen (48 und 84 Aufträge).

Aufruf (aus dem Repo-Ordner):  python tools/messreihe.py [--instances 30] [--out data/messreihe.json] [--only NAME] [--no-large]
Schreibt nach jeder Instanz (Wiederaufnahme: bereits gerechnete Seeds werden übersprungen). Zeitlimit und Prozesszahl stehen in der Datei und im README.
Die Zielwerte unbewiesener Gesamtmodelle können sich zwischen Läufen und Rechnern unterscheiden (Zeitlimit, Prozesse)."""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stp_constants as C  # noqa: E402
import stp_evaluation as ev  # noqa: E402

SEED0 = 1000                     # Seeds der Messreihe: 1000, 1001, ...; die Preset-Seeds der App sind davon unabhängig gewählt
LARGE = [dict(name="48 Aufträge", n_cranes=6, orders_per_crane=8, n_sc=10, instances=4, time_limit=15),
         dict(name="84 Aufträge", n_cranes=6, orders_per_crane=14, n_sc=10, instances=3, time_limit=15)]


def record(a: ev.Analysis, seed: int) -> dict:
    r = {"seed": seed}
    for k, m in a.methods.items():
        r[k] = m.cost.obj
    r["proven"] = {k: m.proven for k, m in a.methods.items()}
    r["wall"] = {k: round(m.wall, 2) for k, m in a.methods.items()}
    r["foreign_g3"] = a.methods["g3"].cost.foreign
    r["cross_arcs"] = int(sum(1 for j in a.inst.orders for p in j.preds if a.pools.crane_pool[a.inst.orders[p].c] != a.pools.crane_pool[j.c]))
    r["reseq"] = bool(a.methods["p0"].resequenced or a.methods["p1"].resequenced)
    return r


def load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"meta": {}, "scenarios": {}, "large": {}}


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", type=int, default=30)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "messreihe.json"))
    ap.add_argument("--only")
    ap.add_argument("--no-large", action="store_true")
    args = ap.parse_args()
    path = Path(args.out)
    data = load(path)
    data["meta"] = {"date": date.today().strftime("%d.%m.%Y"), "instances": args.instances, "time_limit": C.TIME_LIMIT_DEFAULT, "workers": C.WORKERS,
                    "seed0": SEED0, "large_time_limit": 15}
    for name, preset in C.PRESETS.items():
        if args.only and args.only != name:
            continue
        sc = data["scenarios"].setdefault(name, {"settings": {k: v for k, v in preset.items() if k != "seed"}, "records": []})
        sc["settings"] = {k: v for k, v in preset.items() if k != "seed"}
        done = {r["seed"] for r in sc["records"]}
        for seed in range(SEED0, SEED0 + args.instances):
            if seed in done:
                continue
            t = time.time()
            a = ev.analyse(ev.Settings(**{**preset, "seed": seed}))
            sc["records"].append(record(a, seed))
            save(path, data)
            print(f"{name} seed {seed}: {time.time() - t:.1f} s", flush=True)
    if not args.no_large and not args.only:
        for spec in LARGE:
            lg = data["large"].setdefault(spec["name"], {"settings": {k: spec[k] for k in ("n_cranes", "orders_per_crane", "n_sc", "time_limit")}, "records": []})
            done = {r["seed"] for r in lg["records"]}
            for seed in range(SEED0, SEED0 + spec["instances"]):
                if seed in done:
                    continue
                t = time.time()
                base = {**C.PRESETS["Kleiner Hafen"], "n_cranes": spec["n_cranes"], "orders_per_crane": spec["orders_per_crane"], "n_sc": spec["n_sc"],
                        "time_limit": spec["time_limit"], "seed": seed}
                a = ev.analyse(ev.Settings(**base))
                lg["records"].append(record(a, seed))
                save(path, data)
                print(f"{spec['name']} seed {seed}: {time.time() - t:.1f} s", flush=True)
    save(path, data)
    print("fertig:", path)


if __name__ == "__main__":
    main()
