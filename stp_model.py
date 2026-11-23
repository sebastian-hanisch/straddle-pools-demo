"""CP-SAT-Modell: Rundreisen der SC mit Richtzeiten, Abhängigkeiten, Kranreihenfolge und Pools (Gesamtplanung).

Variablen je Auftrag: Zeiten f, a, y, e (siehe stp_timing); je SC eine Rundreise über die Aufträge (AddCircuit mit Auslassen), Zuordnung x[k, j].
Zielwert: Kranverspätung * w_crane + Yard-Verspätung * w_yard + poolfremde Aufträge * Strafe (+ weiche Fristen für Blocker, nur Parallelvarianten).
Das Ergebnis trägt immer seinen Status: bewiesen optimal, oder mit Zeitlimit und der Schranke des Lösers."""

import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

import stp_pools as PL
import stp_terminal as T
import stp_timing as M


@dataclass(frozen=True)
class SolveResult:
    routes: dict | None        # SC -> Auftragsfolge, None wenn keine Lösung gefunden
    obj: float | None
    bound: float | None
    status: str                # "OPTIMAL", "FEASIBLE", "NO_SOLUTION" (Zeitlimit ohne Lösung) oder "INFEASIBLE"
    wall: float
    first_start: dict = field(default_factory=dict)   # Auftrag -> geplanter Beginn der ersten Operation

    @property
    def proven(self) -> bool:
        return self.status == "OPTIMAL"


def _horizon(inst, tk) -> int:
    quay = inst.n_cranes * T.CRANE_SPACING
    far = T.tt((0, 0), (quay, T.YARD_OFFSET + T.YARD_STAGGER))
    return max(tk) + 600 + inst.n_orders * (2 * far + T.SERVICE + T.HAND)


def solve(inst, orders, scs, start_pos, elig, foreign, tk, ty, time_limit: float = 10.0, workers: int = 1, seed: int = 1, hint=None,
          release=None, deadline=None, w_crane: int = M.WEIGHT_CRANE, w_yard: int = M.WEIGHT_YARD, penalty: int = M.PENALTY_FOREIGN) -> SolveResult:
    """Ein Modell über die Aufträge `orders` und die SC `scs` (Listen von IDs).

    elig(k, j): darf SC k den Auftrag j fahren? foreign(k, j): zählt das als poolfremd (Strafe)? hint: Startlösung {SC: Auftragsfolge}.
    release: {Auftrag: frühester Beginn der Stellplatz-Operation}; deadline: {Auftrag: spätester Beginn} als weiche Frist (Gewicht w_crane)."""
    if hint is not None and not isinstance(hint, dict):
        hint = dict(enumerate(hint))
    m = cp_model.CpModel()
    H = _horizon(inst, tk)
    idx = {j: i for i, j in enumerate(orders)}
    orderset = set(orders)
    f, e, y, a, tkv, tyv = {}, {}, {}, {}, {}, {}
    for j in orders:
        order = inst.orders[j]
        f[j], e[j], y[j], a[j] = (m.NewIntVar(0, H, f"{n}{j}") for n in "feya")
        d = T.tt(order.slot, inst.crane_pos[order.c])
        if order.kind == "L":
            m.Add(f[j] == y[j])
            m.Add(a[j] >= y[j] + T.SERVICE + d)
            m.Add(e[j] == a[j] + T.HAND)
        else:
            m.Add(f[j] == a[j])
            m.Add(a[j] >= tk[j])
            m.Add(y[j] >= a[j] + T.HAND + d)
            m.Add(e[j] == y[j] + T.SERVICE)
        if release and j in release:
            m.Add(y[j] >= release[j])
        tkv[j] = m.NewIntVar(0, H, f"tk{j}")
        tyv[j] = m.NewIntVar(0, H, f"ty{j}")
        m.Add(tkv[j] >= a[j] - tk[j])
        m.Add(tyv[j] >= y[j] - ty[j])
    terms = []
    for j, dl in (deadline or {}).items():
        if j in orderset:
            v = m.NewIntVar(0, H, f"dl{j}")
            m.Add(v >= y[j] - dl)
            terms.append(w_crane * v)
    for ids in inst.crane_orders:
        for p, q in zip(ids, ids[1:]):
            if p in orderset and q in orderset:
                m.Add(a[q] >= a[p] + T.HAND)
    for j in orders:
        for p in inst.orders[j].preds:
            if p in orderset:
                m.Add(y[j] >= y[p] + T.SERVICE)
    allp = {}

    def closure(j):
        if j not in allp:
            s = set()
            for p in inst.orders[j].preds:
                s.add(p)
                s |= closure(p)
            allp[j] = s
        return allp[j]

    for j in orders:
        closure(j)
    x, circuits = {}, {}
    for k in scs:
        arcs, lits = [], {}
        unused = m.NewBoolVar(f"unused{k}")
        arcs.append((0, 0, unused))
        for j in orders:
            xv = m.NewBoolVar(f"x{k}_{j}")
            x[k, j] = xv
            if not elig(k, j):
                m.Add(xv == 0)
            arcs.append((idx[j] + 1, idx[j] + 1, xv.Not()))
            l0 = m.NewBoolVar(f"s{k}_{j}")
            lits[-1, j] = l0
            arcs.append((0, idx[j] + 1, l0))
            m.Add(f[j] >= T.tt(start_pos[k], M.pos_first(inst, j))).OnlyEnforceIf(l0)
            l1 = m.NewBoolVar(f"t{k}_{j}")
            lits[j, -1] = l1
            arcs.append((idx[j] + 1, 0, l1))
        for i in orders:
            for j in orders:
                if i == j or j in allp[i] or not (elig(k, i) and elig(k, j)):
                    continue
                lit = m.NewBoolVar(f"r{k}_{i}_{j}")
                lits[i, j] = lit
                arcs.append((idx[i] + 1, idx[j] + 1, lit))
                m.Add(f[j] >= e[i] + T.tt(M.pos_end(inst, i), M.pos_first(inst, j))).OnlyEnforceIf(lit)
        m.AddCircuit(arcs)
        circuits[k] = (lits, unused)
        if hint is not None:
            r = [j for j in hint.get(k, ()) if j in orderset]
            chain, prev = set(), -1
            for j in r:
                chain.add((prev, j))
                prev = j
            chain.add((prev, -1))
            m.AddHint(unused, 1 if not r else 0)
            for key, lit in lits.items():
                m.AddHint(lit, 1 if (r and key in chain) else 0)
            for j in orders:
                m.AddHint(x[k, j], 1 if j in r else 0)
    for j in orders:
        m.AddExactlyOne([x[k, j] for k in scs])
        for k in scs:
            if foreign(k, j):
                terms.append(penalty * x[k, j])
        terms.append(w_crane * tkv[j])
        terms.append(w_yard * tyv[j])
    m.Minimize(sum(terms))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = workers
    s.parameters.random_seed = seed
    t0 = time.time()
    st = s.Solve(m)
    wall = time.time() - t0
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(None, None, None, "INFEASIBLE" if st == cp_model.INFEASIBLE else "NO_SOLUTION", wall)
    routes = {}
    for k in scs:
        lits, _ = circuits[k]
        nxt = {i: j for (i, j), lit in lits.items() if s.Value(lit)}
        r, cur = [], nxt.get(-1, -1)
        while cur != -1:
            r.append(cur)
            cur = nxt.get(cur, -1)
        routes[k] = r
    return SolveResult(routes, s.ObjectiveValue(), s.BestObjectiveBound(), "OPTIMAL" if st == cp_model.OPTIMAL else "FEASIBLE", wall,
                       {j: s.Value(f[j]) for j in orders})


def solve_joint(inst, pools, tk, ty, mode: str, start_pos=None, time_limit: float = 10.0, workers: int = 1, seed: int = 1, hint=None, **weights) -> SolveResult:
    """Gesamtplanung über alle Aufträge. mode: "fest" (SC nur im eigenen Pool; mit einem Pool: kein Pooling) oder "leihen" (poolfremd erlaubt, mit Strafe)."""
    if mode not in ("fest", "leihen"):
        raise ValueError(f"Unbekannter Modus: {mode}")
    sp = start_pos if start_pos is not None else PL.start_positions(inst, pools)
    def own_pool(k, j):
        return pools.sc_pool[k] == PL.pool_of_order(inst, pools, j)

    def anywhere(k, j):
        return True

    def never(k, j):
        return False

    def other_pool(k, j):
        return not own_pool(k, j)

    elig, foreign = (own_pool, never) if mode == "fest" else (anywhere, other_pool)
    return solve(inst, list(range(inst.n_orders)), list(range(pools.n_sc)), sp, elig, foreign, tk, ty, time_limit, workers, seed, hint, **weights)


def routes_list(result: SolveResult, n_sc: int) -> list:
    """Routen als Liste je SC (für stp_timing.evaluate_plan)."""
    return [list(result.routes.get(k, [])) for k in range(n_sc)]
