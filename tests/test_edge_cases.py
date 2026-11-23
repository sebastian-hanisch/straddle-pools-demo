"""Randfälle der Kernroutinen (DEMO-PLAYBOOK §12) und Eigenschaften der Auswertung über alle Verfahren."""

import pytest

import stp_constants as C
import stp_evaluation as ev
import stp_instance as I
import stp_pools as PL


def klein(**kw):
    base = dict(n_cranes=3, orders_per_crane=3, n_sc=4, strategy="adjacent", time_limit=20)
    base.update(kw)
    return ev.Settings(**base)


def test_reihenfolge_der_zielwerte_ueber_alle_verfahren():
    """Alle Teilprobleme bewiesen: G1 <= G3 <= G2 <= P0, P1, Liste; PN <= P1 und PN gleich G2 (G2 ist der Teilraum, in dem PN sucht)."""
    for seed in range(5):
        a = ev.analyse(klein(seed=seed, dep_pct=40, mis_pct=40))
        m = a.methods
        assert all(m[k].proven for k in ("g1", "g2", "g3")), seed
        assert m["g1"].cost.obj <= m["g3"].cost.obj <= m["g2"].cost.obj, seed
        assert m["g2"].cost.obj <= min(m["p0"].cost.obj, m["p1"].cost.obj, m["list"].cost.obj), seed
        assert m["pn"].cost.obj <= m["p1"].cost.obj and m["pn"].proven and m["pn"].cost.obj == m["g2"].cost.obj, seed


def test_zielwert_ist_aus_den_zeiten_nachgerechnet():
    a = ev.analyse(klein(seed=3))
    import stp_timing as M
    for key, mth in a.methods.items():
        foreign = mth.cost.foreign
        w = dict(w_crane=a.settings.w_crane, w_yard=C.W_YARD, penalty=0 if key == "g1" else a.settings.penalty)
        assert M.cost(list(mth.times), a.tk, a.ty, foreign, **w) == mth.cost, key


def test_g1_zaehlt_poolfremde_ohne_strafe_g3_mit_strafe():
    a = ev.analyse(klein(seed=2, dep_pct=40, mis_pct=40, penalty=30))
    g1, g3 = a.methods["g1"].cost, a.methods["g3"].cost
    assert g1.obj == 5 * g1.tard_crane + 1 * g1.tard_yard
    assert g3.obj == 5 * g3.tard_crane + 1 * g3.tard_yard + 30 * g3.foreign


def test_nur_ein_pool_alle_verfahren_gleich():
    a = ev.analyse(klein(n_cranes=2, orders_per_crane=3, n_sc=2, strategy="adjacent", seed=1))
    assert a.pools.n_pools == 1
    obj = {k: m.cost.obj for k, m in a.methods.items()}
    assert obj["g1"] == obj["g2"] == obj["g3"] == obj["p0"] == obj["p1"] == obj["pn"]


def test_ohne_abhaengigkeiten_parallel_gleich_gesamt():
    a = ev.analyse(klein(dep_pct=0, seed=4))
    assert a.inst.n_deps() == 0
    assert a.methods["p0"].cost.obj == a.methods["g2"].cost.obj and not a.methods["p0"].resequenced


def test_kleinste_instanz_ein_kran_ein_sc_ein_auftrag():
    s = ev.Settings(n_cranes=1, orders_per_crane=1, n_sc=1, strategy="per_crane", dep_pct=0, mis_pct=0, seed=0)
    a = ev.analyse(s)
    assert a.inst.n_orders == 1 and all(m.cost.obj == a.methods["g2"].cost.obj for m in a.methods.values())


def test_so_viele_sc_wie_pools_geht_einer_weniger_nicht():
    inst = I.make_instance(0, n_cranes=4, n_per_crane=2)
    PL.make_pools(inst, 4, "per_crane")
    with pytest.raises(ValueError):
        ev.analyse(ev.Settings(n_cranes=4, orders_per_crane=2, n_sc=3, strategy="per_crane"))


def test_zeitlimit_ergebnisse_tragen_den_status_zeitlimit_nie_bewiesen(monkeypatch):
    monkeypatch.setenv(C.MAX_SECONDS_ENV, "0.05")
    a = ev.analyse(ev.Settings(n_cranes=4, orders_per_crane=8, n_sc=6, dep_pct=40, mis_pct=40, seed=5))
    for key in ("g1", "g2", "g3"):
        m = a.methods[key]
        assert m.status in ("Zeitlimit", "Startlösung", "bewiesen")
        assert m.proven == (m.status == "bewiesen")
    assert any(a.methods[k].status != "bewiesen" for k in ("g1", "g2", "g3"))
    assert a.methods["list"].status == "Heuristik" and not a.methods["list"].proven


def test_ergebnis_ist_zulaessig_fuer_jedes_verfahren():
    import stp_timing as M
    a = ev.analyse(klein(seed=6, dep_pct=40, mis_pct=50))
    for key, m in a.methods.items():
        routes = [list(r) for r in m.routes]
        assert sorted(j for r in routes for j in r) == list(range(a.inst.n_orders)), key
        assert M.evaluate_plan(a.inst, routes, a.start_pos, a.tk) is not None, key
