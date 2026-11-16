"""Pool-Zuschnitte (Vorabpooling): welche Kräne bilden einen Pool, wie viele SC gehören zu jedem Pool.

Ein Pool-Zuschnitt ist eine disjunkte Zuordnung Kran -> Pool und SC -> Pool. Jeder Pool hat mindestens einen SC. Die SC-Zahl je Pool folgt der Arbeitslast
(größter Rest), die Arbeitslast eines Krans ist die Summe aus Hin- und Rückfahrt zwischen Kran und Stellplatz, Aufnahme und Übergabe über seine Aufträge."""

import math
from dataclasses import dataclass

import stp_terminal as T

STRATEGIES = ("single", "per_crane", "adjacent", "balanced", "coupled")
STRATEGY_LABELS = {
    "single": "Ein Pool (kein Pooling)",
    "per_crane": "Pool je Kran",
    "adjacent": "Benachbarte Paare",
    "balanced": "Paare nach Arbeitslast",
    "coupled": "Paare nach Kopplung",
}


@dataclass(frozen=True)
class Pools:
    crane_pool: tuple      # Kran -> Pool
    sc_pool: tuple         # SC -> Pool
    n_pools: int

    @property
    def n_sc(self) -> int:
        return len(self.sc_pool)

    def cranes_of(self, p: int) -> tuple:
        return tuple(c for c, q in enumerate(self.crane_pool) if q == p)

    def scs_of(self, p: int) -> tuple:
        return tuple(k for k, q in enumerate(self.sc_pool) if q == p)


def work(inst) -> list:
    """Arbeitslast je Kran in Sekunden (nominal, ohne Wartezeiten)."""
    w = [0] * inst.n_cranes
    for j in inst.jobs:
        w[j.c] += 2 * T.tt(j.slot, inst.crane_pos[j.c]) + T.SERVICE + T.HAND
    return w


def coupling(inst) -> list:
    """Matrix Kran x Kran: Zahl der Abhängigkeiten zwischen Aufträgen der beiden Kräne."""
    c = inst.n_cranes
    mat = [[0] * c for _ in range(c)]
    for j in inst.jobs:
        for p in j.preds:
            a, b = inst.jobs[p].c, j.c
            if a != b:
                mat[a][b] += 1
                mat[b][a] += 1
    return mat


def pair_partitions(cranes: list):
    """Alle Zerlegungen in Paare; bei ungerader Zahl bleibt genau ein Kran allein."""
    if not cranes:
        yield []
        return
    if len(cranes) % 2 == 1:
        for i, single in enumerate(cranes):
            for part in pair_partitions(cranes[:i] + cranes[i + 1:]):
                yield [(single,)] + part
        return
    first, rest = cranes[0], cranes[1:]
    for i, other in enumerate(rest):
        for part in pair_partitions(rest[:i] + rest[i + 1:]):
            yield [(first, other)] + part


def internal_coupling(part, mat) -> int:
    return sum(mat[a][b] for g in part for a in g for b in g if a < b)


def imbalance(part, w) -> int:
    ws = [sum(w[x] for x in g) for g in part]
    return max(ws) - min(ws)


def _groups(inst, strategy: str) -> list:
    c = inst.n_cranes
    if strategy == "single":
        return [tuple(range(c))]
    if strategy == "per_crane":
        return [(x,) for x in range(c)]
    if strategy == "adjacent":
        return [tuple(range(i, min(i + 2, c))) for i in range(0, c, 2)]
    if strategy in ("balanced", "coupled"):
        w, mat = work(inst), coupling(inst)
        parts = list(pair_partitions(list(range(c))))
        if strategy == "balanced":
            best = min(parts, key=lambda p: (imbalance(p, w), p))
        else:
            best = min(parts, key=lambda p: (-internal_coupling(p, mat), imbalance(p, w), p))
        return sorted(tuple(sorted(g)) for g in best)
    raise ValueError(f"Unbekannte Strategie: {strategy}")


def make_pools(inst, n_sc: int, strategy: str) -> Pools:
    """Pool-Zuschnitt nach Strategie; die SC verteilen sich nach Arbeitslast (größter Rest), jeder Pool bekommt mindestens einen SC."""
    groups = _groups(inst, strategy)
    g = len(groups)
    if n_sc < g:
        raise ValueError(f"Mit {g} Pools braucht es mindestens {g} SC")
    w = work(inst)
    total = sum(w) or 1
    shares = [sum(w[x] for x in grp) / total * n_sc for grp in groups]
    counts = [max(1, int(math.floor(s))) for s in shares]
    while sum(counts) > n_sc:
        i = max((i for i in range(g) if counts[i] > 1), key=lambda i: (counts[i] - shares[i], -i))
        counts[i] -= 1
    while sum(counts) < n_sc:
        i = max(range(g), key=lambda i: (shares[i] - counts[i], -i))
        counts[i] += 1
    crane_pool = [0] * inst.n_cranes
    for p, grp in enumerate(groups):
        for x in grp:
            crane_pool[x] = p
    sc_pool = [p for p in range(g) for _ in range(counts[p])]
    return Pools(tuple(crane_pool), tuple(sc_pool), g)


def start_positions(inst, pools: Pools) -> tuple:
    """Jeder SC beginnt am Kai bei seinem ersten Kran des Pools."""
    first = {}
    for c, p in enumerate(pools.crane_pool):
        first.setdefault(p, c)
    return tuple(inst.crane_pos[first[p]] for p in pools.sc_pool)


def pool_of_job(inst, pools: Pools, j: int) -> int:
    return pools.crane_pool[inst.jobs[j].c]


def cross_arcs(inst, pools: Pools) -> int:
    """Zahl der Abhängigkeiten, deren Blocker und Abhängiger in verschiedenen Pools liegen."""
    return sum(1 for job in inst.jobs for p in job.preds if pool_of_job(inst, pools, p) != pool_of_job(inst, pools, job.id))


def foreign_count(inst, pools: Pools, routes) -> int:
    """Zahl der Aufträge, die ein SC außerhalb seines Pools fährt."""
    return sum(1 for k, r in enumerate(routes) for j in r if pools.sc_pool[k] != pool_of_job(inst, pools, j))


def pool_count(n_cranes: int, strategy: str) -> int:
    """Zahl der Pools eines Zuschnitts (hängt nur von der Kranzahl und der Strategie ab): so viele SC braucht der Zuschnitt mindestens."""
    if strategy == "single":
        return 1
    if strategy == "per_crane":
        return n_cranes
    if strategy in ("adjacent", "balanced", "coupled"):
        return (n_cranes + 1) // 2
    raise ValueError(f"Unbekannte Strategie: {strategy}")
