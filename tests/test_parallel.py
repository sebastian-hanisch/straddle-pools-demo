"""Parallelvarianten und Nachbehandlung: zulässige Pläne, Neu-Sequenzierung, Eigenschaften gegen das Optimum der Gesamtplanung."""

import pytest

import stp_heuristic as H
import stp_instance as I
import stp_model as MO
import stp_parallel as PA
import stp_pools as PL
import stp_timing as M
from stp_rng import SplitMix64


def aufbau(seed, c=4, n=2, n_sc=4, strategy="adjacent", dep=40, mis=40):
    inst = I.make_instance(seed, n_cranes=c, n_per_crane=n, dep_pct=dep, mis_pct=mis)
    pools = PL.make_pools(inst, n_sc, strategy)
    tk, ty = M.richtzeiten(inst)
    sp = PL.start_positions(inst, pools)
    hint = H.greedy_plan(inst, pools, sp, tk, ty, "fest")
    return inst, pools, tk, ty, sp, hint


def test_stufen_sind_zulaessige_vollstaendige_plaene():
    for seed in range(6):
        inst, pools, tk, ty, sp, hint = aufbau(seed)
        stages = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=10, rounds=2)
        assert [s.name for s in stages] == ["p0", "p1", "p2"]
        for s in stages:
            assert sorted(j for r in s.routes for j in r) == list(range(inst.n_orders))
            assert M.evaluate_plan(inst, [list(r) for r in s.routes], sp, tk) is not None
            assert PL.foreign_count(inst, pools, s.routes) == 0            # strikt im eigenen Pool
            assert s.cost == M.cost(s.times, tk, ty, 0)


def test_zielwert_nie_besser_als_das_optimum_der_gesamtplanung_mit_festen_pools():
    """Jeder Parallelplan ist ein zulässiger Plan des Gesamtmodells (feste Pools): sein Zielwert liegt nie unter dessen bewiesenem Optimum."""
    for seed in range(8):
        inst, pools, tk, ty, sp, hint = aufbau(seed)
        opt = MO.solve_joint(inst, pools, tk, ty, "fest", sp, time_limit=30)
        assert opt.proven
        for s in PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=10, rounds=1):
            assert s.cost.obj >= opt.obj, (seed, s.name)


def test_ohne_abhaengigkeiten_zwischen_pools_ist_parallel_gleich_gesamt():
    """Ohne poolübergreifende Abhängigkeiten zerfällt die Gesamtplanung mit festen Pools in unabhängige Pool-Probleme: gleiches Optimum."""
    gesehen = 0
    for seed in range(12):
        inst, pools, tk, ty, sp, hint = aufbau(seed, dep=0)
        assert PL.cross_arcs(inst, pools) == 0
        opt = MO.solve_joint(inst, pools, tk, ty, "fest", sp, time_limit=30)
        p0 = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=30, rounds=0)[0]
        assert opt.proven and p0.proven and not p0.resequenced
        assert p0.cost.obj == opt.obj
        gesehen += 1
    assert gesehen == 12


def test_ein_pool_hat_keine_poolgrenze_parallel_gleich_gesamt():
    for seed in range(6):
        inst, pools, tk, ty, sp, hint = aufbau(seed, c=3, n=2, n_sc=2, strategy="single")
        opt = MO.solve_joint(inst, pools, tk, ty, "fest", sp, time_limit=30)
        p0 = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=30, rounds=0)[0]
        assert opt.proven and p0.cost.obj == opt.obj


def test_neu_sequenzierung_liefert_immer_einen_zulaessigen_plan_und_behaelt_die_zuordnung():
    for seed in range(120):
        r = SplitMix64(seed)
        inst = I.make_instance(seed, n_cranes=1 + r.below(4), n_per_crane=1 + r.below(5), dep_pct=r.below(101), mis_pct=r.below(101))
        n_sc = 1 + r.below(4)
        assign = {j: r.below(n_sc) for j in range(inst.n_orders)}
        planned = {j: r.below(500) for j in range(inst.n_orders)}
        routes = PA.resequence(inst, assign, planned, n_sc)
        assert sorted(j for x in routes for j in x) == list(range(inst.n_orders))
        assert all(assign[j] == k for k, x in enumerate(routes) for j in x)
        tk, _ = M.richtzeiten(inst)
        assert M.evaluate_plan(inst, routes, [inst.crane_pos[0]] * n_sc, tk) is not None


def test_neu_sequenzierung_ordnet_nach_geplanter_startzeit():
    inst = I.make_instance(0, n_cranes=2, n_per_crane=1, dep_pct=0)
    routes = PA.resequence(inst, {0: 0, 1: 0}, {0: 50, 1: 10}, 1)
    assert routes == [[1, 0]]
    routes = PA.resequence(inst, {0: 0, 1: 0}, {0: 10, 1: 50}, 1)
    assert routes == [[0, 1]]


def test_freigabezeiten_von_hand():
    """Freigabe nur für Aufträge mit Blocker in einem anderen Pool: Ende der Blocker-Operation (y + SERVICE)."""
    for seed in range(20):
        inst, pools, tk, ty, sp, hint = aufbau(seed, strategy="per_crane", n_sc=4)
        if inst.n_deps() == 0:
            continue
        plan = hint
        times = M.evaluate_plan(inst, plan, sp, tk)
        rel = PA.release_from(inst, pools, times)
        assert rel
        for j, t in rel.items():
            fremd = [p for p in inst.orders[j].preds if PL.pool_of_order(inst, pools, p) != PL.pool_of_order(inst, pools, j)]
            assert fremd and t == max(times[p].y + 15 for p in fremd)
        assert all(any(PL.pool_of_order(inst, pools, p) != PL.pool_of_order(inst, pools, j) for p in inst.orders[j].preds) for j in rel)
        return
    pytest.fail("Kein Fall mit Abhängigkeiten gefunden")


def test_nachoptimierung_ist_nie_schlechter_als_ihre_startloesung_und_gleich_dem_optimum_wenn_bewiesen():
    for seed in range(8):
        inst, pools, tk, ty, sp, hint = aufbau(seed)
        stages = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=10, rounds=1)
        pn = PA.post_optimize(inst, pools, tk, ty, sp, stages[-1], time_limit=30)
        opt = MO.solve_joint(inst, pools, tk, ty, "fest", sp, time_limit=30)
        assert pn.name == "pn" and pn.proven and opt.proven
        assert pn.cost.obj <= stages[-1].cost.obj
        assert pn.cost.obj == opt.obj
        assert pn.wall >= stages[-1].wall


def test_wall_ist_die_laengste_pool_zeit_je_durchgang_und_summe_bleibt_groesser():
    inst, pools, tk, ty, sp, hint = aufbau(2)
    stages = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=10, rounds=1)
    assert 0 <= stages[0].wall <= stages[0].wall_sum
    assert stages[1].wall >= stages[0].wall and stages[1].wall_sum >= stages[0].wall_sum


def test_gleiche_eingabe_gleiche_stufen_mit_einem_prozess():
    inst, pools, tk, ty, sp, hint = aufbau(4)
    a = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=30, rounds=1)
    b = PA.parallel_stages(inst, pools, tk, ty, sp, hint, time_limit=30, rounds=1)
    assert [s.cost for s in a] == [s.cost for s in b]
