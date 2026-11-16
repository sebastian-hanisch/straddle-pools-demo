"""Pool-Zuschnitte: gültige Partitionen, SC-Verteilung, Strategien gegen Aufzählung aller Zerlegungen."""

import pytest

import stp_instance as I
import stp_pools as PL
import stp_terminal as T


def inst4(seed=3):
    return I.make_instance(seed, n_cranes=4, n_per_crane=6, dep_pct=40, mis_pct=30)


@pytest.mark.parametrize("strategy", PL.STRATEGIES)
def test_jede_strategie_gibt_eine_gueltige_partition(strategy):
    for c in (1, 2, 3, 4, 5, 6):
        inst = I.make_instance(c, n_cranes=c, n_per_crane=3, dep_pct=30)
        for n_sc in range(PL._groups(inst, strategy).__len__(), 10):
            pools = PL.make_pools(inst, n_sc, strategy)
            assert len(pools.crane_pool) == c and pools.n_sc == n_sc
            assert sorted(set(pools.crane_pool)) == list(range(pools.n_pools))
            assert sorted(set(pools.sc_pool)) == list(range(pools.n_pools))        # jeder Pool hat Kräne und mindestens einen SC
            assert list(pools.sc_pool) == sorted(pools.sc_pool)


def test_ein_pool_und_pool_je_kran_und_paare():
    inst = inst4()
    assert PL.make_pools(inst, 6, "single").crane_pool == (0, 0, 0, 0)
    assert PL.make_pools(inst, 6, "per_crane").crane_pool == (0, 1, 2, 3)
    assert PL.make_pools(inst, 6, "adjacent").crane_pool == (0, 0, 1, 1)


def test_ungerade_kranzahl_laesst_einen_kran_allein():
    inst = I.make_instance(1, n_cranes=5, n_per_crane=3)
    pools = PL.make_pools(inst, 6, "adjacent")
    assert sorted(len(pools.cranes_of(p)) for p in range(pools.n_pools)) == [1, 2, 2]
    for strategy in ("balanced", "coupled"):
        pools = PL.make_pools(inst, 6, strategy)
        assert sorted(len(pools.cranes_of(p)) for p in range(pools.n_pools)) == [1, 2, 2]


def test_zu_wenige_sc_sind_ein_fehler():
    inst = inst4()
    with pytest.raises(ValueError):
        PL.make_pools(inst, 3, "per_crane")
    assert PL.make_pools(inst, 4, "per_crane").n_pools == 4
    with pytest.raises(ValueError):
        PL.make_pools(inst, 4, "unbekannt")


def test_alle_zerlegungen_in_paare_werden_aufgezaehlt():
    assert len(list(PL.pair_partitions([0, 1, 2, 3]))) == 3
    assert len(list(PL.pair_partitions(list(range(6))))) == 15
    assert len(list(PL.pair_partitions(list(range(5))))) == 15        # 5 Möglichkeiten für den Einzelnen mal 3 Zerlegungen der übrigen vier
    assert list(PL.pair_partitions([])) == [[]]


def test_kopplung_waehlt_die_zerlegung_mit_den_meisten_inneren_abhaengigkeiten():
    for seed in range(20):
        inst = I.make_instance(seed, n_cranes=6, n_per_crane=5, dep_pct=40, mis_pct=30)
        mat = PL.coupling(inst)
        pools = PL.make_pools(inst, 9, "coupled")
        part = [pools.cranes_of(p) for p in range(pools.n_pools)]
        bester = max(PL.internal_coupling(p, mat) for p in PL.pair_partitions(list(range(6))))
        assert PL.internal_coupling(part, mat) == bester


def test_arbeitslast_waehlt_die_ausgeglichenste_zerlegung():
    for seed in range(20):
        inst = I.make_instance(seed, n_cranes=6, n_per_crane=5)
        w = PL.work(inst)
        pools = PL.make_pools(inst, 9, "balanced")
        part = [pools.cranes_of(p) for p in range(pools.n_pools)]
        assert PL.imbalance(part, w) == min(PL.imbalance(p, w) for p in PL.pair_partitions(list(range(6))))


def test_sc_zahl_folgt_der_arbeitslast_und_summiert_sich():
    inst = inst4()
    for strategy in ("per_crane", "adjacent", "balanced", "coupled"):
        for n_sc in range(4, 11):
            pools = PL.make_pools(inst, n_sc, strategy)
            counts = [len(pools.scs_of(p)) for p in range(pools.n_pools)]
            assert sum(counts) == n_sc and min(counts) >= 1
    w = PL.work(inst)
    pools = PL.make_pools(inst, 12, "per_crane")
    mehr = max(range(4), key=lambda c: w[c])
    wenig = min(range(4), key=lambda c: w[c])
    assert len(pools.scs_of(pools.crane_pool[mehr])) >= len(pools.scs_of(pools.crane_pool[wenig]))


def test_kopplungsmatrix_symmetrisch_und_zaehlt_nur_kranuebergreifend():
    inst = inst4()
    mat = PL.coupling(inst)
    assert all(mat[a][b] == mat[b][a] for a in range(4) for b in range(4))
    assert all(mat[a][a] == 0 for a in range(4))
    assert sum(mat[a][b] for a in range(4) for b in range(a + 1, 4)) == inst.n_deps()


def test_arbeitslast_von_hand():
    inst = I.make_instance(0, n_cranes=1, n_per_crane=1, dep_pct=0)
    d = T.tt(inst.jobs[0].slot, inst.crane_pos[0])
    assert PL.work(inst) == [2 * d + T.SERVICE + T.HAND]


def test_startpositionen_am_ersten_kran_des_pools():
    inst = inst4()
    pools = PL.make_pools(inst, 6, "adjacent")
    sp = PL.start_positions(inst, pools)
    assert len(sp) == 6
    for k, p in enumerate(pools.sc_pool):
        assert sp[k] == inst.crane_pos[pools.cranes_of(p)[0]]


def test_kanten_zwischen_pools_und_fremdauftraege():
    inst = inst4()
    ein = PL.make_pools(inst, 6, "single")
    assert PL.cross_arcs(inst, ein) == 0
    je = PL.make_pools(inst, 6, "per_crane")
    assert PL.cross_arcs(inst, je) == inst.n_deps()          # jeder Kran ein Pool: jede Abhängigkeit ist poolübergreifend
    routes = [[] for _ in range(je.n_sc)]
    for j in range(inst.n_jobs):
        routes[je.scs_of(PL.pool_of_job(inst, je, j))[0]].append(j)
    assert PL.foreign_count(inst, je, routes) == 0
    routes[0], routes[-1] = routes[-1], routes[0]
    assert PL.foreign_count(inst, je, routes) > 0
