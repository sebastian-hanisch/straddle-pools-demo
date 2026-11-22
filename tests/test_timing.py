"""Zeitrechnung und Zielwert an handgerechneten Mini-Instanzen (Fahrzeit Kran (20, 0) <-> Stellplatz (20, 110): (110 + 3) // 6 = 18 s)."""

import pytest

import stp_instance as I
import stp_terminal as T
import stp_timing as M
from stp_rng import SplitMix64
from test_oracle_timing import topologischer_plan

SLOT = (20, 110)
CRANE0 = (20, 0)
CRANE1 = (60, 0)


def mini(specs, crane_jobs, crane_pos=(CRANE0, CRANE1)):
    """specs: Liste (Kran, Position, Art, preds); alle Aufträge liegen am Stellplatz SLOT."""
    succs = {i: [] for i in range(len(specs))}
    for i, (_, _, _, preds) in enumerate(specs):
        for p in preds:
            succs[p].append(i)
    jobs = tuple(I.Job(i, c, k, kind, 0, SLOT, tuple(preds), tuple(succs[i])) for i, (c, k, kind, preds) in enumerate(specs))
    return I.Instance(len(crane_jobs), 1, jobs, tuple(tuple(x) for x in crane_jobs), tuple(crane_pos[: len(crane_jobs)]))


def test_fahrzeit_gerundet_symmetrisch_ganzzahlig():
    assert T.tt((0, 0), (0, 0)) == 0
    assert T.tt((0, 0), (2, 0)) == 0          # (2 + 3) // 6
    assert T.tt((0, 0), (3, 0)) == 1          # (3 + 3) // 6
    assert T.tt(CRANE0, SLOT) == 18 == T.tt(SLOT, CRANE0)
    assert isinstance(T.tt((1, 2), (30, 40)), int)


def test_richtzeiten_laden_und_loeschen():
    inst = mini([(0, 0, "L", ()), (0, 1, "D", ())], [[0, 1]])
    tk, ty = M.richtzeiten(inst)
    assert tk == (120, 195)
    assert ty == (120 - 18 - 15, 195 + 20 + 18)       # Laden: Kranzeit minus Fahrt minus Aufnahme; Löschen: Kranzeit plus Übergabe plus Fahrt


def test_laden_ein_auftrag_von_hand():
    """SC startet am Kran: Fahrt 18 -> Aufnahme ab 18, fertig 33 -> Fahrt 18 -> am Kran 51 -> frei ab 71."""
    inst = mini([(0, 0, "L", ())], [[0]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0]], [CRANE0], tk)
    assert t[0] == M.JobTimes(f=18, a=51, y=18, e=71, sc=0)
    assert M.cost(t, tk, ty) == M.Cost(0, 0, 0, 0)


def test_loeschen_wartet_auf_die_richtzeit():
    """SC ist früh am Kran, übernimmt aber erst zur Richtzeit 120: Übergabe 120, am Stellplatz 120 + 20 + 18 = 158, fertig 173."""
    inst = mini([(0, 0, "D", ())], [[0]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0]], [CRANE0], tk)
    assert t[0] == M.JobTimes(f=120, a=120, y=158, e=173, sc=0)
    assert M.cost(t, tk, ty) == M.Cost(0, 0, 0, 0)


def test_verspaetung_wird_gewichtet():
    """SC startet weit weg: Fahrt (1980 + 3) // 6 = 330 -> Übergabe 330 statt 120 (210 s), Stellplatz 368 statt 158 (210 s): 5 * 210 + 1 * 210."""
    inst = mini([(0, 0, "D", ())], [[0]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0]], [(2000, 0)], tk)
    assert (t[0].a, t[0].y) == (330, 368)
    c = M.cost(t, tk, ty)
    assert c == M.Cost(5 * 210 + 210, 210, 210, 0)
    assert M.cost(t, tk, ty, w_crane=2, w_yard=3) == M.Cost(2 * 210 + 3 * 210, 210, 210, 0)


def test_fremdauftraege_kosten_strafe_je_stueck():
    inst = mini([(0, 0, "L", ())], [[0]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0]], [CRANE0], tk)
    assert M.cost(t, tk, ty, foreign=2).obj == 60
    assert M.cost(t, tk, ty, foreign=2, penalty=7).obj == 14


def test_zwei_auftraege_ein_sc_nacheinander():
    """Zweiter Auftrag desselben Krans: SC steht ab 71 am Kran, Fahrt 18 -> 89, Aufnahme 89..104, Fahrt 18 -> 122; Übergabe frühestens 51 + 20 = 71."""
    inst = mini([(0, 0, "L", ()), (0, 1, "L", ())], [[0, 1]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0, 1]], [CRANE0], tk)
    assert t[1] == M.JobTimes(f=89, a=122, y=89, e=142, sc=0)


def test_kranreihenfolge_verzoegert_die_uebergabe():
    """Zwei SC liefern gleichzeitig an einen Kran: Übergaben bei 33 und frühestens 33 + 20 = 53."""
    inst = mini([(0, 0, "L", ()), (0, 1, "L", ())], [[0, 1]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0], [1]], [SLOT, SLOT], tk)
    assert (t[0].a, t[1].a) == (33, 53)


def test_abhaengigkeit_laesst_den_zweiten_sc_warten():
    """Blocker 0 (Kran 0) wird bei 0..15 aufgenommen; Auftrag 1 (Kran 1, gleicher Stapel) darf erst ab 15 aufgenommen werden, Fahrt zu Kran 1: (40 + 110 + 3) // 6 = 25."""
    inst = mini([(0, 0, "L", ()), (1, 0, "L", (0,))], [[0], [1]])
    tk, ty = M.richtzeiten(inst)
    t = M.evaluate_plan(inst, [[0], [1]], [SLOT, SLOT], tk)
    assert (t[0].y, t[1].y) == (0, 15)
    assert t[1].a == 15 + 15 + 25


def test_verklemmung_wird_gemeldet():
    """Auftrag 1 braucht den Stellplatz nach Auftrag 0, steht aber in derselben Route davor: Zeitkreis, kein Plan."""
    inst = mini([(0, 0, "L", ()), (1, 0, "L", (0,))], [[0], [1]])
    tk, ty = M.richtzeiten(inst)
    assert M.evaluate_plan(inst, [[1, 0]], [SLOT], tk) is None
    assert M.evaluate_plan(inst, [[0, 1]], [SLOT], tk) is not None


def test_kreis_ueber_kranreihenfolge_und_route_wird_gemeldet():
    """Route [Auftrag 1 (Position 1), Auftrag 0 (Position 0)] am selben Kran: die Übergabe von 1 wartet auf die von 0, der SC liefert 0 erst nach 1."""
    inst = mini([(0, 0, "L", ()), (0, 1, "L", ())], [[0, 1]])
    tk, ty = M.richtzeiten(inst)
    assert M.evaluate_plan(inst, [[1, 0]], [SLOT], tk) is None


def test_routen_muessen_jeden_auftrag_genau_einmal_enthalten():
    inst = mini([(0, 0, "L", ()), (0, 1, "L", ())], [[0, 1]])
    tk, _ = M.richtzeiten(inst)
    with pytest.raises(ValueError):
        M.evaluate_plan(inst, [[0]], [SLOT], tk)
    with pytest.raises(ValueError):
        M.evaluate_plan(inst, [[0, 1], [1]], [SLOT, SLOT], tk)


def test_zeiten_sind_monoton_und_erfuellen_die_bedingungen_auf_zufallsplaenen():
    """Jede Zeitbedingung des Modells wird einzeln nachgeprüft (nicht nur das Endergebnis), auf zulässigen Zufallsplänen (topologische Reihenfolge)."""
    geprueft = 0
    for seed in range(40):
        inst = I.make_instance(seed, n_cranes=3, n_per_crane=4, dep_pct=40, mis_pct=40)
        rng = SplitMix64(seed + 1000)
        n_sc = 3
        routes = topologischer_plan(inst, n_sc, rng)
        tk, ty = M.richtzeiten(inst)
        start = [inst.crane_pos[0]] * n_sc
        t = M.evaluate_plan(inst, routes, start, tk)
        if t is None:
            continue
        geprueft += 1
        for j, job in enumerate(inst.jobs):
            d = T.tt(job.slot, inst.crane_pos[job.c])
            if job.kind == "L":
                assert t[j].f == t[j].y and t[j].a >= t[j].y + T.SERVICE + d and t[j].e == t[j].a + T.HAND
            else:
                assert t[j].f == t[j].a >= tk[j] and t[j].y >= t[j].a + T.HAND + d and t[j].e == t[j].y + T.SERVICE
            for p in job.preds:
                assert t[j].y >= t[p].y + T.SERVICE
            cp = inst.crane_prev(j)
            if cp is not None:
                assert t[j].a >= t[cp].a + T.HAND
        for k, r in enumerate(routes):
            for i, j in enumerate(r):
                if i:
                    assert t[j].f >= t[r[i - 1]].e + T.tt(M.pos_end(inst, r[i - 1]), M.pos_first(inst, j))
    assert geprueft == 40        # alle Pläne sind zulässig (topologische Reihenfolge)
