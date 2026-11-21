"""Orakel des CP-SAT-Modells: das bewiesene Optimum gegen Aufzählung ALLER Pläne (alle Zuordnungen und Reihenfolgen) auf Mini-Instanzen,
bewertet mit der unabhängigen ereignisdiskreten Simulation aus test_oracle_timing (nicht mit dem Auswerter der Demo). Verglichen wird der Zielwert, nie die Route (Gleichstände)."""

import itertools
import math

import pytest

import stp_instance as I
import stp_model as MO
import stp_pools as PL
import stp_timing as M
from test_oracle_timing import simulate


def alle_plaene(n_jobs, n_sc):
    """Alle Anordnungen der Aufträge auf n_sc geordnete Listen: jede Permutation mit jeder Aufteilung in n_sc Teile (unterschiedliche Anordnungen ergeben nie dieselben Listen)."""
    for perm in itertools.permutations(range(n_jobs)):
        for cuts in itertools.combinations_with_replacement(range(n_jobs + 1), n_sc - 1):
            bounds = (0,) + cuts + (n_jobs,)
            yield [list(perm[bounds[i]:bounds[i + 1]]) for i in range(n_sc)]


def brute_force(inst, pools, tk, ty, sp, mode, penalty=M.PENALTY_FOREIGN, w_crane=M.WEIGHT_CRANE, w_yard=M.WEIGHT_YARD):
    best = math.inf
    for routes in alle_plaene(inst.n_jobs, pools.n_sc):
        fremd = PL.foreign_count(inst, pools, routes)
        if mode == "fest" and fremd:
            continue
        sim = simulate(inst, routes, sp, tk)
        if sim is None:
            continue
        ziel = sum(w_crane * max(0, sim[j][1] - tk[j]) + w_yard * max(0, sim[j][2] - ty[j]) for j in range(inst.n_jobs)) + penalty * fremd
        best = min(best, ziel)
    return best


KONFIG = [
    (dict(n_cranes=5, n_per_crane=1, dep_pct=60, mis_pct=50), 3, "adjacent", 3),
    (dict(n_cranes=4, n_per_crane=1, dep_pct=100, mis_pct=40), 3, "per_crane", 3),   # 4 Pools brauchen 4 SC: siehe unten
    (dict(n_cranes=2, n_per_crane=2, dep_pct=60, mis_pct=50), 2, "per_crane", 5),
    (dict(n_cranes=3, n_per_crane=2, dep_pct=60, mis_pct=30), 2, "adjacent", 2),
]


def fall(konfig):
    kw, n_sc, strategy, n_seeds = konfig
    inst_kw = kw
    for seed in range(n_seeds):
        inst = I.make_instance(seed, **inst_kw)
        sc = max(n_sc, PL._groups(inst, strategy).__len__())
        if sc > 3 and inst.n_jobs > 4:
            continue
        pools = PL.make_pools(inst, sc, strategy)
        yield seed, inst, pools


@pytest.mark.parametrize("mode", ["fest", "leihen"])
def test_optimum_gleicht_der_aufzaehlung_aller_plaene(mode):
    verglichen = 0
    for konfig in KONFIG:
        for seed, inst, pools in fall(konfig):
            tk, ty = M.richtzeiten(inst)
            sp = PL.start_positions(inst, pools)
            r = MO.solve_joint(inst, pools, tk, ty, mode, sp, time_limit=30)
            assert r.proven, (konfig, seed)
            assert r.obj == brute_force(inst, pools, tk, ty, sp, mode), (konfig, seed, mode)
            verglichen += 1
    assert verglichen >= 12


def test_optimum_bei_anderen_gewichten_und_strafen():
    for seed in range(4):
        inst = I.make_instance(seed, n_cranes=2, n_per_crane=2, dep_pct=60, mis_pct=50)
        pools = PL.make_pools(inst, 2, "per_crane")
        tk, ty = M.richtzeiten(inst)
        sp = PL.start_positions(inst, pools)
        for w in (dict(w_crane=1, w_yard=3, penalty=0), dict(w_crane=9, w_yard=1, penalty=100)):
            r = MO.solve_joint(inst, pools, tk, ty, "leihen", sp, time_limit=30, **w)
            assert r.proven and r.obj == brute_force(inst, pools, tk, ty, sp, "leihen", **w), (seed, w)


def test_modellzielwert_gleicht_dem_auswerter_bei_bewiesenem_optimum():
    """Zeiten des Modells und des Auswerters stimmen überein: das Optimum nachgerechnet aus den Routen gibt denselben Zielwert."""
    for seed in range(12):
        inst = I.make_instance(seed, n_cranes=3, n_per_crane=3, dep_pct=40, mis_pct=40)
        pools = PL.make_pools(inst, 4, "adjacent")
        tk, ty = M.richtzeiten(inst)
        sp = PL.start_positions(inst, pools)
        for mode in ("fest", "leihen"):
            r = MO.solve_joint(inst, pools, tk, ty, mode, sp, time_limit=30)
            assert r.proven
            routes = MO.routes_list(r, pools.n_sc)
            t = M.evaluate_plan(inst, routes, sp, tk)
            assert t is not None
            assert M.cost(t, tk, ty, PL.foreign_count(inst, pools, routes)).obj == r.obj, (seed, mode)


def test_eigenschaften_der_modelle():
    """Leihen mit Strafe 0 ist nie schlechter als fest; höhere Strafe nie besser; mit sehr hoher Strafe gleich fest; kleineres Kran-Gewicht nie teurer."""
    for seed in range(6):
        inst = I.make_instance(seed, n_cranes=3, n_per_crane=2, dep_pct=60, mis_pct=40)
        pools = PL.make_pools(inst, 3, "adjacent")
        tk, ty = M.richtzeiten(inst)
        sp = PL.start_positions(inst, pools)
        def opt(mode, **w):
            r = MO.solve_joint(inst, pools, tk, ty, mode, sp, time_limit=30, **w)
            assert r.proven
            return r.obj
        fest = opt("fest")
        assert opt("leihen", penalty=0) <= fest
        assert opt("leihen", penalty=10) <= opt("leihen", penalty=30) <= fest
        assert opt("leihen", penalty=10 ** 6) == fest
        assert opt("fest", w_crane=2) <= fest <= opt("fest", w_crane=9)


def test_zeitlimit_wird_als_status_gemeldet_nie_als_optimum():
    inst = I.make_instance(1, n_cranes=4, n_per_crane=10, dep_pct=40, mis_pct=40)
    pools = PL.make_pools(inst, 4, "per_crane")
    tk, ty = M.richtzeiten(inst)
    sp = PL.start_positions(inst, pools)
    r = MO.solve_joint(inst, pools, tk, ty, "leihen", sp, time_limit=0.05)
    assert r.status in ("FEASIBLE", "NO_SOLUTION") and not r.proven
    if r.routes is not None:
        assert r.bound <= r.obj


def test_startloesung_und_freigabe_und_frist():
    import stp_heuristic as H
    inst = I.make_instance(2, n_cranes=2, n_per_crane=3, dep_pct=60, mis_pct=40)
    pools = PL.make_pools(inst, 2, "per_crane")
    tk, ty = M.richtzeiten(inst)
    sp = PL.start_positions(inst, pools)
    hint = H.greedy_plan(inst, pools, sp, tk, ty, "fest")
    r = MO.solve_joint(inst, pools, tk, ty, "fest", sp, time_limit=30, hint=hint)
    assert r.proven
    # Freigabe: ein Ladeauftrag darf erst später an den Stellplatz (Beginn der Aufnahme = erste Operation)
    j = next(x for x in range(inst.n_jobs) if inst.jobs[x].kind == "L")
    frei = tk[j] + 100
    spaet = MO.solve(inst, list(range(inst.n_jobs)), [0, 1], sp, lambda k, x: pools.sc_pool[k] == PL.pool_of_job(inst, pools, x), lambda k, x: False,
                     tk, ty, 30, release={j: frei})
    assert spaet.proven and spaet.first_start[j] >= frei
    # Frist: sie kostet nur, wenn sie überschritten wird
    plan = M.evaluate_plan(inst, MO.routes_list(r, 2), sp, tk)
    ohne = MO.solve(inst, list(range(inst.n_jobs)), [0, 1], sp, lambda k, x: pools.sc_pool[k] == PL.pool_of_job(inst, pools, x), lambda k, x: False,
                    tk, ty, 30, deadline={x: 10 ** 6 for x in range(inst.n_jobs)})
    assert ohne.obj == r.obj
    streng = MO.solve(inst, list(range(inst.n_jobs)), [0, 1], sp, lambda k, x: pools.sc_pool[k] == PL.pool_of_job(inst, pools, x), lambda k, x: False,
                      tk, ty, 30, deadline={x: 0 for x in range(inst.n_jobs)})
    assert streng.obj > r.obj and plan is not None


def test_unbekannter_modus():
    inst = I.make_instance(0, n_cranes=2, n_per_crane=1)
    pools = PL.make_pools(inst, 2, "per_crane")
    tk, ty = M.richtzeiten(inst)
    with pytest.raises(ValueError):
        MO.solve_joint(inst, pools, tk, ty, "egal")
