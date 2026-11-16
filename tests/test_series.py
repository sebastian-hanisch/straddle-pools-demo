"""Vorgerechnete Messreihe (data/messreihe.json): Aufbau und Eigenschaften, die für jede Instanz gelten müssen (aus den gespeicherten Zielwerten, ohne neu zu rechnen)."""

import pytest

import stp_constants as C
import stp_evaluation as ev

SERIES = ev.load_series()
pytestmark = pytest.mark.skipif(SERIES is None, reason="data/messreihe.json fehlt")


def _alle():
    for name, sc in SERIES["scenarios"].items():
        for r in sc["records"]:
            yield name, r
    for name, sc in SERIES["large"].items():
        for r in sc["records"]:
            yield name, r


def test_aufbau_und_vollstaendigkeit():
    assert set(SERIES["scenarios"]) == set(C.PRESETS)
    n = SERIES["meta"]["instances"]
    for name, sc in SERIES["scenarios"].items():
        assert len(sc["records"]) == n, name
        seeds = [r["seed"] for r in sc["records"]]
        assert seeds == list(range(SERIES["meta"]["seed0"], SERIES["meta"]["seed0"] + n)), name
        assert {k: v for k, v in C.PRESETS[name].items() if k != "seed"} == sc["settings"], name
    assert set(SERIES["large"]) == {"48 Aufträge", "84 Aufträge"}


def test_jede_instanz_hat_alle_verfahren_und_status():
    for name, r in _alle():
        for k in C.METHOD_KEYS:
            assert k in r and isinstance(r[k], int) and r[k] >= 0, (name, r["seed"], k)
            assert k in r["proven"] and k in r["wall"], (name, r["seed"], k)
        assert r["proven"]["list"] is False


def test_ordnung_der_zielwerte_in_jeder_instanz_mit_bewiesenen_gesamtmodellen():
    """Gesamt ohne Pooling <= mit Leihen <= Pools fest <= jede Parallelvariante und Liste; Nachoptimierung nie unter Pools fest (wenn dieses bewiesen ist)."""
    geprueft = 0
    for name, r in _alle():
        if not all(r["proven"][k] for k in ("g1", "g2", "g3")):
            continue
        geprueft += 1
        assert r["g1"] <= r["g3"] <= r["g2"], (name, r["seed"])
        assert r["g2"] <= min(r["p0"], r["p1"], r["list"]), (name, r["seed"])
        assert r["pn"] >= r["g2"], (name, r["seed"])
        assert r["pn"] <= r["p1"], (name, r["seed"])
    assert geprueft >= 90


def test_zeiten_und_zaehler_sind_plausibel():
    for name, r in _alle():
        assert all(w >= 0 for w in r["wall"].values()) and r["wall"]["list"] == 0
        assert 0 <= r["foreign_g3"] <= 100 and r["cross_arcs"] >= 0
        assert r["foreign_g3"] == 0 or r["g3"] <= r["g2"] or not r["proven"]["g3"]
