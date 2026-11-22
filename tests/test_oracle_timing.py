"""Orakel der Zeitrechnung: `stp_timing.evaluate_plan` (kleinste Lösung eines Systems von Zeitbedingungen) gegen eine unabhängige
ereignisgesteuerte Simulation (Uhr, Ereigniswarteschlange, wartende SC). Zwei verschiedene Rechenwege für dieselbe Aussage:
dieselben frühestmöglichen Zeiten, und genau dann keine Lösung, wenn die Simulation in eine Verklemmung läuft.

Die Simulation lässt jeden SC seine Route abfahren; ein SC wartet am Stellplatz auf die Blocker und am Kran auf die Kranreihenfolge
(vorige Übergabe + HAND) und, beim Löschen, auf die Richtzeit. Sie verwendet weder Fixpunkt noch Zeitbedingungen des Auswerters.

Der große Lauf (mindestens 200 Zufallsinstanzen) lief im Scratch-Lauf bei Anlage dieses Tests; im Repo steht die kleine, schnelle Fassung."""

import heapq
import itertools

import stp_instance as I
import stp_terminal as T
import stp_timing as M
from stp_rng import SplitMix64


def simulate(inst, routes, start_pos, tk):
    """Ereignisgesteuerte Simulation; Rückgabe {Auftrag: (f, a, y, e)} oder None bei Verklemmung."""
    heap, seq = [], itertools.count()

    def push(t, kind, *args):
        heapq.heappush(heap, (t, next(seq), kind, args))

    n_sc = len(routes)
    ptr = [0] * n_sc
    pos = list(start_pos)
    started = [0] * inst.n_cranes            # wie viele Aufträge der Kranreihenfolge ihre Übergabe schon begonnen haben
    crane_free = [0] * inst.n_cranes         # frühester Beginn der nächsten Übergabe an diesem Kran
    yard_done = {}                           # Auftrag -> Ende der Stellplatz-Operation
    wait_yard, wait_crane = {}, {}           # Auftrag -> wartender SC
    out = {}
    finished = [0]

    def next_job(k, t):
        if ptr[k] == len(routes[k]):
            finished[0] += 1
            return
        j = routes[k][ptr[k]]
        push(t + T.tt(pos[k], M.pos_first(inst, j)), "arrive_first", k, j)

    def try_yard(k, j, t):
        if all(p in yard_done for p in inst.jobs[j].preds):
            out.setdefault(j, {})["y"] = t
            if inst.jobs[j].kind == "L":
                out[j]["f"] = t
            push(t + T.SERVICE, "yard_end", k, j)
        else:
            wait_yard[j] = k

    def try_crane(k, j, t):
        job = inst.jobs[j]
        c = job.c
        if job.k == started[c] and t >= crane_free[c] and (job.kind == "L" or t >= tk[j]):
            started[c] += 1
            crane_free[c] = t + T.HAND
            out.setdefault(j, {})["a"] = t
            if job.kind == "D":
                out[j]["f"] = t
            push(t + T.HAND, "handoff_end", k, j)
            push(t + T.HAND, "crane_wake", c)
        else:
            wait_crane[j] = k
            if job.kind == "D" and t < tk[j]:
                push(tk[j], "crane_wake", c)

    for k in range(n_sc):
        next_job(k, 0)
    while heap:
        t, _, kind, args = heapq.heappop(heap)
        if kind == "arrive_first":
            k, j = args
            (try_yard if inst.jobs[j].kind == "L" else try_crane)(k, j, t)
        elif kind == "yard_end":
            k, j = args
            yard_done[j] = t
            job = inst.jobs[j]
            if job.kind == "L":
                push(t + T.tt(job.slot, inst.crane_pos[job.c]), "arrive_crane", k, j)
            else:
                out[j]["e"] = t
                pos[k] = job.slot
                ptr[k] += 1
                next_job(k, t)
            for w in [w for w in list(wait_yard) if all(p in yard_done for p in inst.jobs[w].preds)]:
                try_yard(wait_yard.pop(w), w, t)
        elif kind == "arrive_crane":
            k, j = args
            try_crane(k, j, t)
        elif kind == "crane_wake":
            (c,) = args
            if started[c] < len(inst.crane_jobs[c]):
                j = inst.crane_jobs[c][started[c]]
                if j in wait_crane:
                    try_crane(wait_crane.pop(j), j, t)
        elif kind == "handoff_end":
            k, j = args
            job = inst.jobs[j]
            if job.kind == "L":
                out[j]["e"] = t
                pos[k] = inst.crane_pos[job.c]
                ptr[k] += 1
                next_job(k, t)
            else:
                push(t + T.tt(inst.crane_pos[job.c], job.slot), "arrive_slot", k, j)
        elif kind == "arrive_slot":
            k, j = args
            try_yard(k, j, t)
    if finished[0] < n_sc:
        return None
    return {j: (v["f"], v["a"], v["y"], v["e"]) for j, v in out.items()}


def topologischer_plan(inst, n_sc, rng):
    """Zufälliger zulässiger Plan: Aufträge in zufälliger topologischer Reihenfolge (Kranketten und Abhängigkeiten) auf zufällige SC verteilt."""
    placed, routes = set(), [[] for _ in range(n_sc)]
    while len(placed) < inst.n_jobs:
        bereit = [j.id for j in inst.jobs if j.id not in placed and all(p in placed for p in j.preds)
                  and (inst.crane_prev(j.id) is None or inst.crane_prev(j.id) in placed)]
        j = bereit[rng.below(len(bereit))]
        routes[rng.below(n_sc)].append(j)
        placed.add(j)
    return routes


def gestoerter_plan(inst, n_sc, rng):
    """Wie topologischer_plan, danach zwei Aufträge derselben Route vertauscht (kann eine Verklemmung erzeugen oder nicht)."""
    routes = topologischer_plan(inst, n_sc, rng)
    langer = [k for k, r in enumerate(routes) if len(r) >= 2]
    if langer:
        r = routes[langer[rng.below(len(langer))]]
        i, j = rng.below(len(r)), rng.below(len(r))
        r[i], r[j] = r[j], r[i]
    return routes


def vergleiche(seed, n_cranes=3, n_per=4, n_sc=3, dep=40, mis=40, gestoert=True):
    inst = I.make_instance(seed, n_cranes=n_cranes, n_per_crane=n_per, dep_pct=dep, mis_pct=mis)
    rng = SplitMix64(seed * 7919 + 13)
    routes = (gestoerter_plan if gestoert and seed % 2 else topologischer_plan)(inst, n_sc, rng)
    start = [inst.crane_pos[rng.below(n_cranes)] for _ in range(n_sc)]
    tk, _ = M.richtzeiten(inst)
    fix = M.evaluate_plan(inst, routes, start, tk)
    sim = simulate(inst, routes, start, tk)
    return fix, sim


def test_ereignissimulation_gleicht_dem_auswerter_auf_zufallsplaenen():
    machbar = verklemmt = 0
    for seed in range(80):
        fix, sim = vergleiche(seed)
        assert (fix is None) == (sim is None), seed
        if fix is None:
            verklemmt += 1
            continue
        machbar += 1
        for j, t in enumerate(fix):
            assert (t.f, t.a, t.y, t.e) == sim[j], (seed, j)
    assert machbar >= 40 and verklemmt >= 3          # beide Ausgänge kommen vor: der Vergleich prüft Zeiten und Verklemmungen


def test_ereignissimulation_an_der_handinstanz():
    """Dieselbe Handrechnung wie in test_timing: Löschen mit Richtzeit 120 gibt Übergabe 120, Stellplatz 158, frei 173."""
    inst = I.make_instance(0, n_cranes=1, n_per_crane=1, dep_pct=0)
    job = inst.jobs[0]
    d = T.tt(job.slot, inst.crane_pos[0])
    tk, _ = M.richtzeiten(inst)
    sim = simulate(inst, [[0]], [inst.crane_pos[0]], tk)
    a = max(T.tt(inst.crane_pos[0], M.pos_first(inst, 0)), tk[0]) if job.kind == "D" else None
    if job.kind == "D":
        assert sim[0] == (120, 120, 120 + T.HAND + d, 120 + T.HAND + d + T.SERVICE) and a == 120
    else:
        y = T.tt(inst.crane_pos[0], job.slot)
        assert sim[0] == (y, y + T.SERVICE + d, y, y + T.SERVICE + d + T.HAND)


def test_randfaelle_ein_sc_viele_sc_keine_abhaengigkeit():
    for n_sc in (1, 2, 6):
        for dep in (0, 100):
            for seed in range(8):
                fix, sim = vergleiche(seed, n_sc=n_sc, dep=dep)
                assert (fix is None) == (sim is None)
                if fix is not None:
                    assert all((t.f, t.a, t.y, t.e) == sim[j] for j, t in enumerate(fix))


def test_gleichstand_zweier_sc_am_kran_gibt_dieselbe_reihenfolge():
    """Zwei SC erreichen den Kran gleichzeitig: die Kranreihenfolge (Position in der Kranreihenfolge) entscheidet, nicht die Reihenfolge der Ereignisse."""
    inst = I.make_instance(4, n_cranes=1, n_per_crane=2, dep_pct=0)
    tk, _ = M.richtzeiten(inst)
    for routes in ([[0], [1]], [[1], [0]]):
        start = [inst.crane_pos[0]] * 2
        fix = M.evaluate_plan(inst, routes, start, tk)
        sim = simulate(inst, routes, start, tk)
        assert (fix is None) == (sim is None)
        if fix is not None:
            assert all((t.f, t.a, t.y, t.e) == sim[j] for j, t in enumerate(fix))
