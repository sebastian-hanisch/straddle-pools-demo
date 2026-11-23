"""Strikt parallele Pool-Rechnung mit Nachbehandlung der Abhängigkeiten über Pools hinweg.

Jeder Pool plant seine Aufträge allein (eigenes CP-SAT-Modell, ohne Abhängigkeiten zu anderen Pools). Als Rechenzeit der parallelen Rechnung zählt die längste Pool-Zeit
(angenommen: alle Pools rechnen gleichzeitig; hier nacheinander gemessen). Die Nachbehandlung rechnet die Zeiten des zusammengesetzten Plans mit allen Abhängigkeiten neu
(ein SC wartet am Stellplatz auf den Blocker); gibt es dabei eine Verklemmung, wird die Reihenfolge je SC nach geplanter Startzeit unter Beachtung aller Vorrangbedingungen neu gebildet.

Stufen:
  p0  Pools ignorieren fremde Abhängigkeiten, Nachbehandlung wie oben.
  p1  dazu eine Runde: jeder Pool rechnet noch einmal, mit den Fertigzeiten fremder Blocker aus dem Plan von p0 als Freigaben.
  pn  globale Nachoptimierung: das Gesamtmodell (feste Pools) mit dem Plan der letzten Stufe als Startlösung und Zeitlimit."""

from dataclasses import dataclass

import stp_model as MO
import stp_pools as PL
import stp_terminal as T
import stp_timing as M


@dataclass(frozen=True)
class Stage:
    name: str
    routes: tuple           # je SC die Auftragsfolge
    times: tuple            # OrderTimes je Auftrag
    cost: M.Cost
    wall: float             # Rechenzeit bis hierher (längste Pool-Zeit je Durchgang, über die Durchgänge summiert)
    wall_sum: float         # Summe aller Pool-Zeiten (wie bei nacheinander gerechneten Pools)
    resequenced: bool       # Nachbehandlung musste die Reihenfolge neu bilden (Verklemmung im zusammengesetzten Plan)
    proven: bool            # alle beteiligten Teilmodelle bewiesen optimal


def resequence(inst, assign: dict, planned_f: dict, n_sc: int) -> list:
    """Reihenfolge je SC neu bilden: SC-Zuordnung bleibt, Aufträge nach geplanter Startzeit, Vorrang durch Abhängigkeiten und Kranreihenfolge (immer zeitkreisfrei)."""
    placed = set()
    routes = [[] for _ in range(n_sc)]
    while len(placed) < inst.n_orders:
        cand = [j for j in range(inst.n_orders) if j not in placed and all(p in placed for p in inst.orders[j].preds)
                and (inst.crane_prev(j) is None or inst.crane_prev(j) in placed)]
        j = min(cand, key=lambda x: (planned_f[x], x))
        routes[assign[j]].append(j)
        placed.add(j)
    return routes


def release_from(inst, pools, times) -> dict:
    """Freigabezeiten: für jeden Auftrag mit Blockern in anderen Pools das späteste Ende einer fremden Blocker-Operation laut Plan."""
    release = {}
    for order in inst.orders:
        fr = [times[p].y + T.SERVICE for p in order.preds if PL.pool_of_order(inst, pools, p) != PL.pool_of_order(inst, pools, order.id)]
        if fr:
            release[order.id] = max(fr)
    return release


def _pool_pass(inst, pools, sp, tk, ty, time_limit, workers, seed, release, hint, weights):
    routes, assign, planned, walls, proven = {}, {}, {}, [], True
    for p in range(pools.n_pools):
        orders = [j.id for j in inst.orders if PL.pool_of_order(inst, pools, j.id) == p]
        scs = list(pools.scs_of(p))
        r = MO.solve(inst, orders, scs, sp, lambda k, j: True, lambda k, j: False, tk, ty, time_limit, workers, seed, hint, release=release or None, **weights)
        if r.routes is None:
            return None
        walls.append(r.wall)
        proven &= r.proven
        for k, rt in r.routes.items():
            routes[k] = rt
            for j in rt:
                assign[j] = k
        planned.update(r.first_start)
    return routes, assign, planned, max(walls), sum(walls), proven


def _finish(inst, pools, sp, tk, ty, routes: dict, assign, planned, weights):
    plan = [list(routes.get(k, [])) for k in range(pools.n_sc)]
    times = M.evaluate_plan(inst, plan, sp, tk)
    reseq = False
    if times is None:
        plan = resequence(inst, assign, planned, pools.n_sc)
        times = M.evaluate_plan(inst, plan, sp, tk)
        reseq = True
    return plan, times, reseq


def _stage(name, plan, times, tk, ty, pools, inst, wall, wall_sum, reseq, proven, weights) -> Stage:
    foreign = PL.foreign_count(inst, pools, plan)
    return Stage(name, tuple(tuple(r) for r in plan), tuple(times), M.cost(times, tk, ty, foreign, **weights), wall, wall_sum, reseq, proven)


def parallel_stages(inst, pools, tk, ty, start_pos, hint, time_limit: float = 10.0, workers: int = 1, seed: int = 1, rounds: int = 1, **weights) -> list:
    """Stufen p0, p1 (bei rounds >= 1; weitere Runden heißen p2, p3 ...). hint: Startlösung je SC (z. B. das gierige Verfahren, fest)."""
    first = _pool_pass(inst, pools, start_pos, tk, ty, time_limit, workers, seed, None, hint, weights)
    if first is None:
        return []
    routes, assign, planned, wall, wall_sum, proven = first
    plan, times, reseq = _finish(inst, pools, start_pos, tk, ty, routes, assign, planned, weights)
    stages = [_stage("p0", plan, times, tk, ty, pools, inst, wall, wall_sum, reseq, proven, weights)]
    for r in range(1, rounds + 1):
        nxt = _pool_pass(inst, pools, start_pos, tk, ty, time_limit, workers, seed, release_from(inst, pools, stages[-1].times), stages[-1].routes, weights)
        if nxt is None:
            break
        routes, assign, planned, w, ws, proven = nxt
        plan, times, reseq = _finish(inst, pools, start_pos, tk, ty, routes, assign, planned, weights)
        stages.append(_stage(f"p{r}", plan, times, tk, ty, pools, inst, stages[-1].wall + w, stages[-1].wall_sum + ws, reseq, proven, weights))
    return stages


def post_optimize(inst, pools, tk, ty, start_pos, base: Stage, time_limit: float = 10.0, workers: int = 1, seed: int = 1, **weights) -> Stage | None:
    """pn: Gesamtmodell mit festen Pools, Startlösung = Plan der Stufe `base`."""
    r = MO.solve_joint(inst, pools, tk, ty, "fest", start_pos, time_limit, workers, seed, hint=list(base.routes), **weights)
    if r.routes is None:
        return None
    plan = MO.routes_list(r, pools.n_sc)
    times = M.evaluate_plan(inst, plan, start_pos, tk)
    return _stage("pn", plan, times, tk, ty, pools, inst, base.wall + r.wall, base.wall_sum + r.wall, False, r.proven, weights)
