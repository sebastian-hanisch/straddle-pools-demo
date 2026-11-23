"""Gieriges Listenverfahren nach Richtzeit: die einfachste faire Regel und Startlösung der CP-SAT-Modelle.

Aufträge in Reihenfolge der Kran-Richtzeit (Vorrang: Abhängigkeiten und Kranreihenfolge); jeder Auftrag geht an den zulässigen SC, bei dem seine gewichtete
Verspätung bei exakten Zeiten der schon geplanten Aufträge am kleinsten ist (Gleichstand: früheres Freiwerden, dann kleinere SC-Nummer)."""

import stp_pools as PL
import stp_terminal as T
import stp_timing as M


def greedy_plan(inst, pools, start_pos, tk, ty, mode: str = "fest", w_crane: int = M.WEIGHT_CRANE, w_yard: int = M.WEIGHT_YARD,
                penalty: int = M.PENALTY_FOREIGN) -> list:
    """Routen je SC. mode: "fest" (nur eigener Pool) oder "leihen" (alle SC dürfen alles, poolfremd kostet die Strafe)."""
    if mode not in ("fest", "leihen"):
        raise ValueError(f"Unbekannter Modus: {mode}")
    n = inst.n_orders
    routes = [[] for _ in range(pools.n_sc)]
    last = [None] * pools.n_sc
    placed = {}
    while len(placed) < n:
        cand = [j for j in range(n) if j not in placed and all(p in placed for p in inst.orders[j].preds)
                and (inst.crane_prev(j) is None or inst.crane_prev(j) in placed)]
        j = min(cand, key=lambda x: (tk[x], x))
        order = inst.orders[j]
        d = T.tt(order.slot, inst.crane_pos[order.c])
        dep_ready = max((placed[p]["y"] + T.SERVICE for p in order.preds), default=0)
        cpj = inst.crane_prev(j)
        ap = placed[cpj]["a"] + T.HAND if cpj is not None else 0
        best = None
        for k in range(pools.n_sc):
            foreign = pools.sc_pool[k] != PL.pool_of_order(inst, pools, j)
            if foreign and mode == "fest":
                continue
            if last[k] is None:
                arr = T.tt(start_pos[k], M.pos_first(inst, j))
            else:
                pj = last[k]
                arr = placed[pj]["e"] + T.tt(M.pos_end(inst, pj), M.pos_first(inst, j))
            if order.kind == "L":
                yv = max(arr, dep_ready)
                av = max(yv + T.SERVICE + d, ap)
                ev = av + T.HAND
            else:
                av = max(arr, tk[j], ap)
                yv = max(av + T.HAND + d, dep_ready)
                ev = yv + T.SERVICE
            c = w_crane * max(0, av - tk[j]) + w_yard * max(0, yv - ty[j]) + (penalty if foreign else 0)
            key = (c, ev, k)
            if best is None or key < best[0]:
                best = (key, k, {"a": av, "y": yv, "e": ev})
        _, k, t = best
        routes[k].append(j)
        last[k] = j
        placed[j] = t
    return routes
