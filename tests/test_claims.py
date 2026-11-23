"""Jede Zahl der Tabelle „Befunde“ in der README, nachgerechnet aus der gespeicherten Messreihe (data/messreihe.json) mit denselben Auswertungsfunktionen wie die App
(`stp_evaluation.series_stats`). Der Test sucht den erwarteten Text in der README: ändert sich die Messreihe oder die README, schlägt er an."""

import statistics as st
from pathlib import Path

import pytest

import stp_evaluation as ev

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
SERIES = ev.load_series()
pytestmark = pytest.mark.skipif(SERIES is None, reason="data/messreihe.json fehlt")


def komma(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def median_ratio(records, a, b) -> float:
    return st.median((r[a] + 1) / (r[b] + 1) for r in records)


def recs(name):
    return SERIES["scenarios"][name]["records"]


def in_readme(text):
    assert text in README, text


def test_messreihe_angaben():
    m = SERIES["meta"]
    in_readme(f"**{m['instances']} erzeugte Instanzen**")
    in_readme(f"Zeitlimit {m['time_limit']} s je Modell, {m['workers']} CP-SAT-Prozesse, gerechnet am {m['date']}")
    in_readme(f"Zufalls-Seeds {m['seed0']} bis {m['seed0'] + m['instances'] - 1}")


def test_zuschnitt():
    r = recs("Kleiner Hafen")
    in_readme(f"das {komma(median_ratio(r, 'g2', 'g1'))}-Fache der Gesamtplanung ohne Pooling, mit Leihen das {komma(median_ratio(r, 'g3', 'g1'))}-Fache")
    in_readme(f"in {sum(x['proven']['g1'] for x in r)} von {len(r)} Instanzen bewiesen optimal, mit Leihen in {sum(x['proven']['g3'] for x in r)}")
    e = recs("Zu enge Pools")
    in_readme(f"Median {komma(median_ratio(e, 'g2', 'g1'))}-fach bei festen Pools, {komma(median_ratio(e, 'g3', 'g1'))}-fach mit Leihen")
    in_readme(f"Das gierige Verfahren kostet im Median das {komma(median_ratio(r, 'list', 'g2'))}-Fache von G2")


def test_reichlich_sc():
    r = recs("Reichlich SC")
    gleich = sum(1 for x in r if x["g1"] == x["g2"] == x["g3"])
    assert gleich == len(r) == 30
    in_readme(f"in {gleich} von {len(r)} Instanzen denselben Zielwert")


def test_parallel_verteilung():
    assert all(ev.series_stats(recs(n), "p1")["n"] == 30 for n in SERIES["scenarios"])
    k = ev.series_stats(recs("Kleiner Hafen"), "p1")
    in_readme(f"in Kleiner Hafen in {k['equal']} von {k['n']} Instanzen gleich G2 und in {k['double']} von {k['n']} mehr als doppelt so teuer (größter Aufschlag {ev.de(k['worst'])} Zielwertpunkte)")
    g, s_, e, r_ = (ev.series_stats(recs(n), "p1") for n in ("Gute Stapelung", "Schlechte Stapelung", "Zu enge Pools", "Reichlich SC"))
    in_readme(f"Gute Stapelung {g['equal']} und {g['double']} von 30")
    in_readme(f"Schlechte Stapelung {s_['equal']} und {s_['double']} von 30 (größter Aufschlag {ev.de(s_['worst'])})")
    in_readme(f"Zu enge Pools {e['equal']} und {e['double']} von 30")
    in_readme(f"Reichlich SC {r_['equal']} und {r_['double']} von 30")
    p0k, p0s = ev.series_stats(recs("Kleiner Hafen"), "p0"), ev.series_stats(recs("Schlechte Stapelung"), "p0")
    in_readme(f"in Kleiner Hafen in {p0k['equal']} von 30 Instanzen gleich G2 und in {p0k['double']} von 30 mehr als doppelt so teuer; Schlechte Stapelung {p0s['equal']} und {p0s['double']} von 30")
    in_readme(f"Mittel von Parallel + Runde {ev.de(k['mean_key'])} gegen {ev.de(k['mean_ref'])} für G2, aber in {k['equal']} von 30 Instanzen gleich")


def test_nachoptimierung():
    for name, sc in SERIES["scenarios"].items():
        s = ev.series_stats(sc["records"], "pn")
        assert s["equal"] == s["n"] == 30, name
    in_readme("erreicht in allen fünf Szenarien in 30 von 30 Instanzen den Zielwert von G2")
    proven = [sum(x["proven"]["g2"] for x in sc["records"]) for sc in SERIES["scenarios"].values()]
    in_readme(f"G2 ist dabei in {min(proven)} bis {max(proven)} von 30 Instanzen je Szenario bewiesen optimal")


def test_rechenzeit():
    r = recs("Kleiner Hafen")
    mean = lambda k: st.mean(x["wall"][k] for x in r)  # noqa: E731
    median = lambda k: st.median(x["wall"][k] for x in r)  # noqa: E731
    in_readme(f"im Median: Parallel + Runde {komma(median('p1'), 1)} s, G2 {komma(median('g2'), 1)} s, PN {komma(median('pn'), 1)} s")
    in_readme(f"(im Mittel {komma(mean('p1'), 1)} s, {komma(mean('g2'), 1)} s, {komma(mean('pn'), 1)} s)")
    g2 = [x["wall"]["g2"] for x in r]
    in_readme(f"in {sum(1 for t in g2 if t < 0.5)} von 30 Instanzen unter 0,5 s, in {sum(1 for t in g2 if t > 2)} mehr als 2 s, in {sum(1 for x in r if not x['proven']['g2'])} das Zeitlimit")
    in_readme(f"das Mittel ohne diese 2 Instanzen ist {komma(st.mean(x['wall']['g2'] for x in r if x['proven']['g2']), 1)} s")


def test_grosse_instanzen():
    lg = SERIES["large"]["84 Aufträge"]["records"]
    assert len(lg) == 3 and sum(x["proven"][k] for x in lg for k in ("g1", "g2", "g3")) == 0
    mean = lambda k: st.mean(x[k] for x in lg)  # noqa: E731
    in_readme(f"G2 im Mittel {ev.de(mean('g2'))}; das Modell ohne Pooling (Mittel {ev.de(mean('g1'))})")
    p1 = [x["p1"] / x["g2"] for x in lg]
    pn = [x["pn"] / x["g2"] for x in lg]
    in_readme(f"Parallel + Runde liegt je Instanz beim {komma(min(p1))}- bis {komma(max(p1))}-Fachen von G2, PN beim {komma(min(pn))}- bis {komma(max(pn))}-Fachen")
    in_readme(f"Verhältnis der Mittel {komma(mean('p1') / mean('g2'))} und {komma(mean('pn') / mean('g2'))}")
    in_readme("kein Gesamtmodell bewiesen")


def test_grosse_instanzen_g1_und_g3_blieben_beim_startplan():
    """„verbesserten den gierigen Startplan in keiner Instanz“: der gespeicherte Zielwert von G1 und G3 ist der des gierigen Startplans (Leihen mit Strafe 0 bzw. mit Strafe), nur G2 ist besser als sein Start."""
    import stp_constants as C
    import stp_heuristic as H
    import stp_instance as I
    import stp_pools as PL
    import stp_timing as M
    spec = SERIES["large"]["84 Aufträge"]
    in_readme("verbesserten den gierigen Startplan in keiner Instanz, nur G2 tat es")
    for r in spec["records"]:
        s = ev.Settings(**{**C.PRESETS["Kleiner Hafen"], **{k: spec["settings"][k] for k in ("n_cranes", "orders_per_crane", "n_sc", "time_limit")}, "seed": r["seed"]})
        inst = I.make_instance(s.seed, s.n_cranes, s.orders_per_crane, C.N_BLOCKS, s.dep_pct, s.mis_pct)
        pools = PL.make_pools(inst, s.n_sc, s.strategy)
        tk, ty = M.richtzeiten(inst)
        sp = PL.start_positions(inst, pools)
        w = dict(w_crane=s.w_crane, w_yard=C.W_YARD)
        free = H.greedy_plan(inst, pools, sp, tk, ty, "leihen", penalty=0, **w)
        lend = H.greedy_plan(inst, pools, sp, tk, ty, "leihen", penalty=s.penalty, **w)
        fest = H.greedy_plan(inst, pools, sp, tk, ty, "fest", penalty=s.penalty, **w)
        assert r["g1"] == M.cost(M.evaluate_plan(inst, free, sp, tk), tk, ty, 0, penalty=0, **w).obj
        assert r["g3"] == M.cost(M.evaluate_plan(inst, lend, sp, tk), tk, ty, PL.foreign_count(inst, pools, lend), penalty=s.penalty, **w).obj
        assert r["g2"] < M.cost(M.evaluate_plan(inst, fest, sp, tk), tk, ty, 0, penalty=s.penalty, **w).obj


def test_spannen_der_verhaeltnisse():
    r = recs("Kleiner Hafen")
    q = [(x["g2"] + 1) / (x["g1"] + 1) for x in r]
    in_readme(f"Spanne des Verhältnisses fest zu ohne Pooling je Instanz {komma(min(q), 1)} bis {ev.de(max(q))}")
    e = [(x["g2"] + 1) / (x["g1"] + 1) for x in recs("Zu enge Pools")]
    in_readme(f"Spanne des Verhältnisses fest zu ohne Pooling {komma(min(e), 1)} bis {ev.de(max(e))}")
