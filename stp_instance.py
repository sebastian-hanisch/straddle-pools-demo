"""Instanzen: Auftragsreihenfolgen je Kran, Stellplätze und Stapel-Abhängigkeiten, deterministisch aus dem Zufalls-Seed (SplitMix64).

Auftrag: Art L (Laden: vom Stellplatz zum Kran) oder D (Löschen: vom Kran zum Stellplatz), ein Block, die Stellplatz-Position.
Abhängigkeit a -> b: die Stellplatz-Operation von b beginnt erst, wenn die von a beendet ist (Container b liegt unter a im selben Stapel).
Abhängigkeiten gibt es nur zwischen Aufträgen gleicher Art an verschiedenen Kränen und nie so, dass zusammen mit den Kranreihenfolgen ein Kreis entsteht."""

from dataclasses import dataclass

import stp_terminal as T
from stp_rng import SplitMix64


@dataclass(frozen=True)
class Job:
    id: int
    c: int                 # Kran
    k: int                 # Position in der Kranreihenfolge (0 = zuerst) (0 = zuerst)
    kind: str              # "L" oder "D"
    block: int
    slot: tuple            # Stellplatz-Position (x, y)
    preds: tuple           # Aufträge, deren Stellplatz-Operation zuerst beendet sein muss
    succs: tuple


@dataclass(frozen=True)
class Instance:
    n_cranes: int
    n_blocks: int
    jobs: tuple
    crane_jobs: tuple      # je Kran: Auftrags-IDs in der Reihenfolge der Positionen
    crane_pos: tuple

    @property
    def n_jobs(self) -> int:
        return len(self.jobs)

    def crane_prev(self, j: int):
        job = self.jobs[j]
        return self.crane_jobs[job.c][job.k - 1] if job.k > 0 else None

    def n_deps(self) -> int:
        return sum(len(j.preds) for j in self.jobs)


def _creates_cycle(crane_jobs, succs, kinds_c, a: int, b: int) -> bool:
    """Würde die Kante a -> b einen Kreis schließen (Kranketten + Abhängigkeiten)? Gibt es schon einen Weg b ~> a?"""
    seen, stack = set(), [b]
    while stack:
        x = stack.pop()
        if x == a:
            return True
        if x in seen:
            continue
        seen.add(x)
        stack.extend(succs[x])
        c, k = kinds_c[x]
        if k + 1 < len(crane_jobs[c]):
            stack.append(crane_jobs[c][k + 1])
    return False


def make_instance(seed: int, n_cranes: int = 4, n_per_crane: int = 6, n_blocks: int = 6, dep_pct: int = 30, mis_pct: int = 30) -> Instance:
    """Instanz aus (Zufalls-Seed, Größe).

    dep_pct: Anteil der Aufträge in Stapelpaaren (ganze Prozent, 0 bis 100; höchstens die Hälfte der Aufträge kann Blocker sein).
    mis_pct: Anteil der Paare, die gegen die Bedarfsreihenfolge gestapelt sind: der später benötigte Container liegt oben und muss zuerst weg."""
    if n_cranes < 1 or n_per_crane < 1 or n_blocks < 1:
        raise ValueError("Kräne, Aufträge je Kran und Blöcke müssen mindestens 1 sein")
    if not (0 <= dep_pct <= 100 and 0 <= mis_pct <= 100):
        raise ValueError("Prozentwerte liegen zwischen 0 und 100")
    rng = SplitMix64(seed)
    n = n_cranes * n_per_crane
    cranes = [i // n_per_crane for i in range(n)]
    ks = [i % n_per_crane for i in range(n)]
    kind = ["L" if rng.below(2) == 0 else "D" for _ in range(n)]
    block = [rng.below(n_blocks) for _ in range(n)]
    crane_jobs = tuple(tuple(range(c * n_per_crane, (c + 1) * n_per_crane)) for c in range(n_cranes))
    where = {i: (cranes[i], ks[i]) for i in range(n)}
    succs = [[] for _ in range(n)]
    preds = [[] for _ in range(n)]
    n_pairs = (dep_pct * n + 100) // 200
    used = set()
    pairs = 0
    tries = 0
    while pairs < n_pairs and tries < 50 * max(1, n_pairs) and n >= 2:
        tries += 1
        a = rng.below(n)
        b = rng.below(n - 1)
        if b >= a:
            b += 1
        if a in used or b in used or cranes[a] == cranes[b] or kind[a] != kind[b]:
            continue
        first, second = (a, b) if (ks[a] < ks[b] or (ks[a] == ks[b] and rng.below(2) == 0)) else (b, a)
        if rng.below(100) < mis_pct:
            first, second = second, first
        if _creates_cycle(crane_jobs, succs, where, first, second):
            continue
        used.update((a, b))
        pairs += 1
        block[b] = block[a]            # beide Container stehen im selben Stapel
        succs[first].append(second)
        preds[second].append(first)
    jobs = tuple(
        Job(i, cranes[i], ks[i], kind[i], block[i], T.block_position(block[i], n_blocks, n_cranes), tuple(sorted(preds[i])), tuple(sorted(succs[i])))
        for i in range(n)
    )
    return Instance(n_cranes, n_blocks, jobs, crane_jobs, tuple(T.crane_position(c) for c in range(n_cranes)))


def is_acyclic(inst: Instance) -> bool:
    """Prüft, dass Kranreihenfolgen und Abhängigkeiten zusammen keinen Kreis bilden (Kahn-Verfahren)."""
    indeg = {j.id: len(j.preds) + (1 if j.k > 0 else 0) for j in inst.jobs}
    ready = [j for j, d in indeg.items() if d == 0]
    seen = 0
    while ready:
        x = ready.pop()
        seen += 1
        nxt = list(inst.jobs[x].succs)
        job = inst.jobs[x]
        if job.k + 1 < len(inst.crane_jobs[job.c]):
            nxt.append(inst.crane_jobs[job.c][job.k + 1])
        for q in nxt:
            indeg[q] -= 1
            if indeg[q] == 0:
                ready.append(q)
    return seen == inst.n_jobs
