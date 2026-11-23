"""Gieriges Listenverfahren: zulässige Pläne, Pool-Treue, Grenzen gegen das bewiesene Optimum."""

import pytest

import stp_heuristic as H
import stp_instance as I
import stp_model as MO
import stp_pools as PL
import stp_timing as M


def aufbau(seed, c=3, n=3, n_sc=4, strategy="adjacent", dep=40, mis=40):
    inst = I.make_instance(seed, n_cranes=c, n_per_crane=n, dep_pct=dep, mis_pct=mis)
    pools = PL.make_pools(inst, n_sc, strategy)
    tk, ty = M.richtzeiten(inst)
    return inst, pools, tk, ty, PL.start_positions(inst, pools)


@pytest.mark.parametrize("mode", ["fest", "leihen"])
def test_plan_ist_zulaessig_und_vollstaendig(mode):
    for seed in range(25):
        inst, pools, tk, ty, sp = aufbau(seed)
        routes = H.greedy_plan(inst, pools, sp, tk, ty, mode)
        assert sorted(j for r in routes for j in r) == list(range(inst.n_orders))
        assert M.evaluate_plan(inst, routes, sp, tk) is not None


def test_fest_haelt_die_pools_ein_leihen_darf_sie_verlassen():
    fremd_gesehen = False
    for seed in range(40):
        inst, pools, tk, ty, sp = aufbau(seed, n_sc=4)
        fest = H.greedy_plan(inst, pools, sp, tk, ty, "fest")
        assert PL.foreign_count(inst, pools, fest) == 0
        leihen = H.greedy_plan(inst, pools, sp, tk, ty, "leihen", penalty=0)
        fremd_gesehen |= PL.foreign_count(inst, pools, leihen) > 0
    assert fremd_gesehen


def test_hohe_strafe_ohne_vorteil_gibt_den_festen_plan():
    for seed in range(15):
        inst, pools, tk, ty, sp = aufbau(seed)
        fest = H.greedy_plan(inst, pools, sp, tk, ty, "fest")
        leihen = H.greedy_plan(inst, pools, sp, tk, ty, "leihen", penalty=10 ** 9)
        assert leihen == fest


def test_deterministisch():
    inst, pools, tk, ty, sp = aufbau(3)
    assert H.greedy_plan(inst, pools, sp, tk, ty) == H.greedy_plan(inst, pools, sp, tk, ty)


def test_nie_besser_als_das_bewiesene_optimum():
    for seed in range(8):
        inst, pools, tk, ty, sp = aufbau(seed, c=2, n=3, n_sc=2, strategy="per_crane", dep=60)
        r = MO.solve_joint(inst, pools, tk, ty, "fest", sp, time_limit=20)
        assert r.proven
        plan = H.greedy_plan(inst, pools, sp, tk, ty, "fest")
        ziel = M.cost(M.evaluate_plan(inst, plan, sp, tk), tk, ty).obj
        assert ziel >= r.obj


def test_unbekannter_modus_und_ein_auftrag():
    inst, pools, tk, ty, sp = aufbau(0)
    with pytest.raises(ValueError):
        H.greedy_plan(inst, pools, sp, tk, ty, "egal")
    inst = I.make_instance(0, n_cranes=1, n_per_crane=1, dep_pct=0)
    pools = PL.make_pools(inst, 1, "single")
    tk, ty = M.richtzeiten(inst)
    assert H.greedy_plan(inst, pools, PL.start_positions(inst, pools), tk, ty) == [[0]]
