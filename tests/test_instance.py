"""Instanzgenerator: Aufbau, Abhängigkeiten, Wiederholbarkeit, Randfälle."""

import pytest

import stp_instance as I
import stp_terminal as T


def test_groesse_und_reihenfolge_je_kran():
    inst = I.make_instance(3, n_cranes=3, n_per_crane=5)
    assert inst.n_jobs == 15 and len(inst.crane_jobs) == 3
    for c, ids in enumerate(inst.crane_jobs):
        assert [inst.jobs[j].k for j in ids] == list(range(5))
        assert all(inst.jobs[j].c == c for j in ids)
    assert [j.id for j in inst.jobs] == list(range(15))


def test_gleicher_seed_gleiche_instanz_anderer_seed_andere():
    assert I.make_instance(11) == I.make_instance(11)
    assert I.make_instance(11) != I.make_instance(12)


def test_anzahl_der_paare_folgt_dem_anteil():
    """Anteil 30 % von 24 Aufträgen: (30 * 24 + 100) // 200 = 4 Paare, also 4 Abhängigkeiten (für diese Seeds ohne Kreis-Ausfälle)."""
    assert all(I.make_instance(s, dep_pct=30).n_deps() == 4 for s in range(10))


def test_ohne_abhaengigkeiten_bei_anteil_null():
    for s in range(10):
        inst = I.make_instance(s, dep_pct=0)
        assert inst.n_deps() == 0 and all(j.preds == () and j.succs == () for j in inst.jobs)


def test_abhaengigkeiten_gleiche_art_verschiedene_krane_gleicher_stellplatz():
    for s in range(40):
        inst = I.make_instance(s, dep_pct=40, mis_pct=50)
        for job in inst.jobs:
            for p in job.preds:
                other = inst.jobs[p]
                assert other.kind == job.kind and other.c != job.c
                assert other.slot == job.slot and other.block == job.block
                assert job.id in other.succs


def test_preds_und_succs_sind_spiegelbildlich():
    inst = I.make_instance(5, dep_pct=40)
    for job in inst.jobs:
        assert all(job.id in inst.jobs[p].succs for p in job.preds)
        assert all(job.id in inst.jobs[q].preds for q in job.succs)


def test_nie_ein_kreis_mit_den_kranketten():
    for s in range(60):
        inst = I.make_instance(s, n_cranes=4, n_per_crane=6, dep_pct=40, mis_pct=50)
        assert I.is_acyclic(inst), s


def test_is_acyclic_erkennt_einen_kreis():
    """Zwei Kräne, je zwei Aufträge, Ketten 0 -> 1 und 2 -> 3. Die Abhängigkeiten 0 -> 3 allein bilden keinen Kreis; 1 -> 2 und 3 -> 0 schließen ihn (0 -> 1 -> 2 -> 3 -> 0)."""
    inst = I.make_instance(0, n_cranes=2, n_per_crane=2, dep_pct=0)
    jobs = list(inst.jobs)
    def job(i, preds, succs):
        j = jobs[i]
        return I.Job(j.id, j.c, j.k, j.kind, j.block, j.slot, tuple(preds), tuple(succs))
    # Kette Kran 0: 0 -> 1; Kran 1: 2 -> 3; Abhängigkeiten 1 -> 2 und 3 -> 0
    kreis = I.Instance(inst.n_cranes, inst.n_blocks, (job(0, [3], []), job(1, [], [2]), job(2, [1], []), job(3, [], [0])), inst.crane_jobs, inst.crane_pos)
    assert not I.is_acyclic(kreis)
    ok = I.Instance(inst.n_cranes, inst.n_blocks, (job(0, [], [3]), job(1, [], []), job(2, [], []), job(3, [0], [])), inst.crane_jobs, inst.crane_pos)
    assert I.is_acyclic(ok)


def test_gegen_die_bedarfsreihenfolge_gestapelt_nur_bei_mis_anteil():
    """Ohne Fehlstapel zeigt jede Abhängigkeit vom früher benötigten zum später benötigten Auftrag (kleinere oder gleiche Position in der Kranreihenfolge)."""
    for s in range(30):
        inst = I.make_instance(s, dep_pct=40, mis_pct=0)
        for job in inst.jobs:
            for p in job.preds:
                assert inst.jobs[p].k <= job.k
    gegen = 0
    for s in range(30):
        inst = I.make_instance(s, dep_pct=40, mis_pct=100)
        gegen += sum(1 for job in inst.jobs for p in job.preds if inst.jobs[p].k > job.k)
    assert gegen > 0          # bei 100 % Fehlstapel zeigt mindestens eine Abhängigkeit gegen die Bedarfsreihenfolge


def test_stellplaetze_liegen_im_yard():
    inst = I.make_instance(1, n_blocks=6)
    for job in inst.jobs:
        assert job.slot[1] >= T.YARD_OFFSET and 0 <= job.block < 6
        assert 0 <= job.slot[0] <= inst.n_cranes * T.CRANE_SPACING


def test_randfaelle_ein_kran_eine_position():
    inst = I.make_instance(0, n_cranes=1, n_per_crane=1)
    assert inst.n_jobs == 1 and inst.n_deps() == 0 and I.is_acyclic(inst)
    zwei = I.make_instance(0, n_cranes=1, n_per_crane=2, dep_pct=100)
    assert zwei.n_deps() == 0          # ein Kran: keine Abhängigkeit zwischen verschiedenen Kränen möglich


def test_ungueltige_eingaben():
    with pytest.raises(ValueError):
        I.make_instance(0, n_cranes=0)
    with pytest.raises(ValueError):
        I.make_instance(0, dep_pct=101)
    with pytest.raises(ValueError):
        I.make_instance(0, mis_pct=-1)
