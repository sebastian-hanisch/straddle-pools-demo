"""Die Schnellstart-Szenarien live: jeder Zufalls-Seed liefert die Geschichte, die sein Hilfetext erzählt (Abnahmekriterien aus tools/PRESET_SWEEP.md).

Gerechnet wird mit dem vollen Zeitlimit der Voreinstellung (nicht mit der Test-Obergrenze), denn die Aussagen gelten für bewiesene Optima."""

import pytest

import stp_constants as C
import stp_evaluation as ev
import stp_pools as PL


@pytest.fixture(scope="module", autouse=True)
def volles_zeitlimit():
    import os
    alt = os.environ.pop(C.MAX_SECONDS_ENV, None)
    yield
    if alt is not None:
        os.environ[C.MAX_SECONDS_ENV] = alt


@pytest.fixture(scope="module")
def analysen():
    return {name: ev.analyse(ev.Settings(**p)) for name, p in C.PRESETS.items()}


def test_ordnung_in_jedem_szenario(analysen):
    for name, a in analysen.items():
        m = a.methods
        if all(m[k].proven for k in ("g1", "g2", "g3")):
            assert m["g1"].cost.obj <= m["g3"].cost.obj <= m["g2"].cost.obj, name
        assert m["g2"].cost.obj <= min(m["p0"].cost.obj, m["p1"].cost.obj, m["list"].cost.obj), name


def test_kleiner_hafen_ist_typisch(analysen):
    a = analysen["Kleiner Hafen"]
    assert ev.Settings(**C.PRESETS["Kleiner Hafen"]) == ev.Settings()
    assert a.obj("g2") > a.obj("g1") and a.obj("g3") < a.obj("g2")


def test_gute_stapelung_hat_keine_fehlstapel(analysen):
    a = analysen["Gute Stapelung"]
    assert a.settings.mis_pct == 0
    assert all(a.inst.jobs[p].k <= j.k for j in a.inst.jobs for p in j.preds)


def test_schlechte_stapelung_zeigt_den_aufschlag(analysen):
    a = analysen["Schlechte Stapelung"]
    assert ev.is_double(a.obj("p1"), a.obj("g2"))
    assert ev.verdict_parallel(a)[0] == "warning"


def test_zu_enge_pools_ist_ein_pool_je_kran_und_leihen_hilft(analysen):
    a = analysen["Zu enge Pools"]
    assert a.pools.n_pools == a.inst.n_cranes and PL.cross_arcs(a.inst, a.pools) == a.inst.n_deps()
    assert a.obj("g2") >= 5 * a.obj("g1")
    assert ev.verdict_leihen(a)[0] == "success"


def test_reichlich_sc_alle_gesamtverfahren_gleich(analysen):
    a = analysen["Reichlich SC"]
    assert a.obj("g1") == a.obj("g2") == a.obj("g3")
    assert ev.verdict_zuschnitt(a)[0] == "success"


def test_jedes_szenario_hat_ein_verdikt_je_frage(analysen):
    for name, a in analysen.items():
        for fn in (ev.verdict_zuschnitt, ev.verdict_leihen, ev.verdict_parallel):
            kind, text = fn(a)
            assert kind in ("success", "info", "warning") and text, (name, fn.__name__)
