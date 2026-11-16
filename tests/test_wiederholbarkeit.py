"""Wiederholbarkeit der parallelen Verfahren (data/wiederholbarkeit.json): die Zahlen des README-Abschnitts „Wiederholbarkeit“, nachgerechnet."""

import json
from pathlib import Path

import pytest

import stp_evaluation as ev

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
try:
    W = json.loads((ROOT / "data" / "wiederholbarkeit.json").read_text(encoding="utf-8"))
except FileNotFoundError:
    W = None
pytestmark = pytest.mark.skipif(W is None, reason="data/wiederholbarkeit.json fehlt")


def lauf(name, i):
    """Die Instanzen eines Szenarios mit dem Zielwert von P0 und P1 für den i-ten Zufallswert des Lösers und dem gespeicherten G2."""
    return [dict(g2=r["g2"], p0=r["p0"][i], p1=r["p1"][i]) for r in W["scenarios"][name]["records"]]


def bereich(werte):
    lo, hi = min(werte), max(werte)
    return f"{lo}" if lo == hi else f"{lo} bis {hi}"


def test_aufbau():
    assert W["meta"]["solver_seeds"] == [1, 2, 3] and set(W["scenarios"]) == {"Kleiner Hafen", "Schlechte Stapelung"}
    for sc in W["scenarios"].values():
        assert len(sc["records"]) == 30 and all(all(r["pools_proven"]) for r in sc["records"])


def test_anzahl_der_instanzen_mit_anderem_ergebnis():
    k, s = W["scenarios"]["Kleiner Hafen"]["records"], W["scenarios"]["Schlechte Stapelung"]["records"]
    chg = lambda recs, key: sum(1 for r in recs if len(set(r[key])) > 1)  # noqa: E731
    assert (chg(k, "p0"), chg(k, "p1"), chg(s, "p0"), chg(s, "p1")) == (17, 4, 20, 13)
    assert (f"ändert sich P0 in {chg(k, 'p0')} von 30 Instanzen und P1 in {chg(k, 'p1')}, in Schlechte Stapelung P0 in {chg(s, 'p0')} und P1 in {chg(s, 'p1')}") in README


def test_verteilung_je_lauf():
    stats = {n: [(ev.series_stats(lauf(n, i), "p0"), ev.series_stats(lauf(n, i), "p1")) for i in range(3)] for n in W["scenarios"]}
    k0, k1 = zip(*stats["Kleiner Hafen"])
    s0, s1 = zip(*stats["Schlechte Stapelung"])
    assert f"in Kleiner Hafen in {bereich([x['equal'] for x in k1])} von 30 Instanzen gleich G2 und in {bereich([x['double'] for x in k1])} von 30 mehr als doppelt so teuer" in README
    assert f"in Schlechte Stapelung in {bereich([x['equal'] for x in s1])} gleich und in {bereich([x['double'] for x in s1])} mehr als doppelt" in README
    assert f"P0 ist in Kleiner Hafen in {bereich([x['equal'] for x in k0])} gleich und in {bereich([x['double'] for x in k0])} mehr als doppelt" in README
    assert f"in Schlechte Stapelung in {bereich([x['equal'] for x in s0])} gleich und in {bereich([x['double'] for x in s0])} mehr als doppelt" in README
    worst = [x["worst"] for x in s1]
    assert f"zwischen {ev.de(min(worst))} und {ev.de(max(worst))}" in README


def test_die_verteilung_bleibt_in_jedem_lauf_bestehen():
    """Die Aussage „ein Teil gleich, ein Teil sehr teuer“ gilt für P1 in jedem der drei Läufe beider Szenarien."""
    for n in W["scenarios"]:
        for i in range(3):
            s1 = ev.series_stats(lauf(n, i), "p1")
            assert s1["equal"] >= 10 and s1["double"] >= 4, (n, i)
