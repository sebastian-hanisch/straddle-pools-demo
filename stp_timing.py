"""Zeitrechnung eines Plans und Zielwert (reine Rechnung, kein Streamlit).

Ein Plan ist eine Liste von Routen: routes[k] ist die Reihenfolge der Aufträge (IDs) des SC k. Gerechnet werden die frühestmöglichen Zeiten
als kleinste Lösung aller Zeitbedingungen, auf Ereignisebene je Auftrag:

    f  Beginn der ersten Operation (L: Aufnahme am Stellplatz, D: Übergabe am Kran)
    a  Beginn der Übergabe am Kran
    y  Beginn der Stellplatz-Operation
    e  Zeitpunkt, zu dem der SC wieder frei ist

Bedingungen: Fahrzeiten zwischen den Operationen, Abhängigkeiten (y des Abhängigen >= y des Blockers + SERVICE), Kranreihenfolge (a des nächsten Auftrags
der Kranreihenfolge >= a des vorigen + HAND), beim Löschen frühestens zur Richtzeit am Kran. Gibt es keine Lösung (Zeitkreis, Verklemmung), ist das Ergebnis None."""

from typing import NamedTuple

import stp_terminal as T

WEIGHT_CRANE = 5        # Gewicht der Verspätung am Kran (Annahme, Regler der App)
WEIGHT_YARD = 1         # Gewicht der Verspätung am Yard
PENALTY_FOREIGN = 30    # Strafe je poolfremdem Auftrag (Notlösung)


class OrderTimes(NamedTuple):
    f: int
    a: int
    y: int
    e: int
    sc: int


class Cost(NamedTuple):
    obj: int
    tard_crane: int
    tard_yard: int
    foreign: int


def pos_first(inst, j: int) -> tuple:
    order = inst.orders[j]
    return order.slot if order.kind == "L" else inst.crane_pos[order.c]


def pos_end(inst, j: int) -> tuple:
    order = inst.orders[j]
    return inst.crane_pos[order.c] if order.kind == "L" else order.slot


def richtzeiten(inst) -> tuple:
    """Richtzeit am Kran = LEAD + Position * CYCLE; Richtzeit am Yard = Kranzeit minus (Laden) bzw. plus (Löschen) die nominale Fahrt samt Operation."""
    tk, ty = [], []
    for order in inst.orders:
        t = T.LEAD + order.k * T.CYCLE
        d = T.tt(order.slot, inst.crane_pos[order.c])
        tk.append(t)
        ty.append(t - d - T.SERVICE if order.kind == "L" else t + T.HAND + d)
    return tuple(tk), tuple(ty)


def check_routes(inst, routes) -> None:
    """Jeder Auftrag steht genau einmal in genau einer Route."""
    seen = [j for r in routes for j in r]
    if sorted(seen) != list(range(inst.n_orders)):
        raise ValueError("Jeder Auftrag muss genau einmal in den Routen stehen")


def evaluate_plan(inst, routes, start_pos, tk):
    """Früheste Zeiten bei festen Routen; Liste von OrderTimes je Auftrag, oder None bei Verklemmung (Zeitkreis)."""
    check_routes(inst, routes)
    n = inst.n_orders
    sc_of = [0] * n
    sc_prev = [None] * n
    for k, r in enumerate(routes):
        for i, j in enumerate(r):
            sc_of[j] = k
            sc_prev[j] = r[i - 1] if i else None
    t = {}
    for j in range(n):
        for key in "faye":
            t[key, j] = 0
        if inst.orders[j].kind == "D":
            t["a", j] = tk[j]
    cons = []      # (Ziel, Quelle oder None, Konstante): t[Ziel] >= t[Quelle] + Konstante
    for j in range(n):
        order = inst.orders[j]
        d = T.tt(order.slot, inst.crane_pos[order.c])
        if order.kind == "L":
            cons += [(("f", j), ("y", j), 0), (("y", j), ("f", j), 0), (("a", j), ("y", j), T.SERVICE + d), (("e", j), ("a", j), T.HAND)]
        else:
            cons += [(("f", j), ("a", j), 0), (("a", j), ("f", j), 0), (("y", j), ("a", j), T.HAND + d), (("e", j), ("y", j), T.SERVICE)]
        if sc_prev[j] is None:
            cons.append((("f", j), None, T.tt(start_pos[sc_of[j]], pos_first(inst, j))))
        else:
            p = sc_prev[j]
            cons.append((("f", j), ("e", p), T.tt(pos_end(inst, p), pos_first(inst, j))))
        for p in order.preds:
            cons.append((("y", j), ("y", p), T.SERVICE))
        cp = inst.crane_prev(j)
        if cp is not None:
            cons.append((("a", j), ("a", cp), T.HAND))
    for _ in range(4 * n + 8):
        changed = False
        for tgt, src, c in cons:
            v = (t[src] if src is not None else 0) + c
            if v > t[tgt]:
                t[tgt] = v
                changed = True
        if not changed:
            break
    else:
        return None
    return [OrderTimes(t["f", j], t["a", j], t["y", j], t["e", j], sc_of[j]) for j in range(n)]


def cost(times, tk, ty, foreign: int = 0, w_crane: int = WEIGHT_CRANE, w_yard: int = WEIGHT_YARD, penalty: int = PENALTY_FOREIGN) -> Cost:
    """Zielwert = Kranverspätung * w_crane + Yard-Verspätung * w_yard + poolfremde Aufträge * Strafe (Verspätungen als Summe über Aufträge, in Sekunden)."""
    tard_k = sum(max(0, times[j].a - tk[j]) for j in range(len(times)))
    tard_y = sum(max(0, times[j].y - ty[j]) for j in range(len(times)))
    return Cost(w_crane * tard_k + w_yard * tard_y + penalty * foreign, tard_k, tard_y, foreign)
