"""Auswertung (kein Streamlit): alle Verfahren auf einer Instanz rechnen, Kennzahlen, Verdikte als reine Funktionen, Statistik der vorgerechneten Reihe."""

import json
from dataclasses import dataclass
from pathlib import Path

import stp_constants as C
import stp_heuristic as H
import stp_instance as I
import stp_model as MO
import stp_parallel as PA
import stp_pools as PL
import stp_timing as M

SERIES_PATH = Path(__file__).resolve().parent / "data" / "messreihe.json"


@dataclass(frozen=True)
class Settings:
    n_cranes: int = C.N_CRANES_DEFAULT
    jobs_per_crane: int = C.JOBS_PER_CRANE_DEFAULT
    n_sc: int = C.N_SC_DEFAULT
    dep_pct: int = C.DEP_PCT_DEFAULT
    mis_pct: int = C.MIS_PCT_DEFAULT
    strategy: str = C.STRATEGY_DEFAULT
    w_crane: int = C.W_CRANE_DEFAULT
    penalty: int = C.PENALTY_DEFAULT
    time_limit: int = C.TIME_LIMIT_DEFAULT
    seed: int = C.SEED_DEFAULT


@dataclass(frozen=True)
class Method:
    key: str
    cost: M.Cost
    wall: float            # Rechenzeit (parallel: längste Pool-Zeit je Durchgang)
    wall_sum: float
    proven: bool           # bewiesen optimal (Listenverfahren: nie)
    status: str            # "bewiesen", "Zeitlimit", "Startlösung" (das Modell lieferte in der Zeit keine Lösung, der Startplan bleibt), "Heuristik", "Teilmodelle bewiesen" oder "Teilmodelle Zeitlimit" (parallele Verfahren)
    routes: tuple
    times: tuple
    resequenced: bool = False
    bound: float | None = None      # Schranke des Lösers (nur Gesamtmodelle); bei bewiesenem Optimum gleich dem Zielwert (ohne Gewicht der Fristen)


@dataclass(frozen=True)
class Analysis:
    settings: Settings
    inst: I.Instance
    pools: PL.Pools
    tk: tuple
    ty: tuple
    start_pos: tuple
    methods: dict          # Schlüssel -> Method

    def obj(self, key: str) -> int:
        return self.methods[key].cost.obj


# ---------------------------------------------------------------- Rechnung
def _weights(s: Settings) -> dict:
    return dict(w_crane=s.w_crane, w_yard=C.W_YARD, penalty=s.penalty)


def _from_solve(key, r, inst, pools, sp, tk, ty, hint_plan, weights) -> Method:
    if r.routes is None:       # Zeitlimit ohne Lösung: die Startlösung bleibt der Plan
        plan, status, proven = [list(x) for x in hint_plan], "Startlösung", False
    else:
        plan, status, proven = MO.routes_list(r, pools.n_sc), ("bewiesen" if r.proven else "Zeitlimit"), r.proven
    times = M.evaluate_plan(inst, plan, sp, tk)
    foreign = PL.foreign_count(inst, pools, plan)
    cost = M.cost(times, tk, ty, foreign, **({**weights, "penalty": 0} if key == "g1" else weights))
    return Method(key, cost, r.wall, r.wall, proven, status, tuple(tuple(x) for x in plan), tuple(times), bound=r.bound)


def analyse(s: Settings) -> Analysis:
    """Alle sieben Verfahren auf der Instanz zu den Einstellungen. Wirft ValueError, wenn der Zuschnitt mehr Pools als SC hat."""
    inst = I.make_instance(s.seed, s.n_cranes, s.jobs_per_crane, C.N_BLOCKS, s.dep_pct, s.mis_pct)
    pools = PL.make_pools(inst, s.n_sc, s.strategy)
    tk, ty = M.richtzeiten(inst)
    sp = PL.start_positions(inst, pools)
    w = _weights(s)
    tl = C.time_limit(s.time_limit)
    hint_fest = H.greedy_plan(inst, pools, sp, tk, ty, "fest", **w)
    hint_frei = H.greedy_plan(inst, pools, sp, tk, ty, "leihen", w_crane=s.w_crane, w_yard=C.W_YARD, penalty=0)
    hint_leihen = H.greedy_plan(inst, pools, sp, tk, ty, "leihen", **w)
    methods = {}
    times = M.evaluate_plan(inst, hint_fest, sp, tk)
    methods["list"] = Method("list", M.cost(times, tk, ty, 0, **w), 0.0, 0.0, False, "Heuristik", tuple(tuple(x) for x in hint_fest), tuple(times))
    g1 = MO.solve_joint(inst, pools, tk, ty, "leihen", sp, tl, C.WORKERS, hint=hint_frei, **{**w, "penalty": 0})
    methods["g1"] = _from_solve("g1", g1, inst, pools, sp, tk, ty, hint_frei, w)
    g2 = MO.solve_joint(inst, pools, tk, ty, "fest", sp, tl, C.WORKERS, hint=hint_fest, **w)
    methods["g2"] = _from_solve("g2", g2, inst, pools, sp, tk, ty, hint_fest, w)
    g3 = MO.solve_joint(inst, pools, tk, ty, "leihen", sp, tl, C.WORKERS, hint=hint_leihen, **w)
    methods["g3"] = _from_solve("g3", g3, inst, pools, sp, tk, ty, hint_leihen, w)
    stages = PA.parallel_stages(inst, pools, tk, ty, sp, hint_fest, tl, C.WORKERS, rounds=1, **w)
    for st in stages:
        # Die parallelen Pläne sind Heuristiken: auch wenn jedes Pool-Modell bewiesen optimal ist, ist der zusammengesetzte Plan nicht als optimal bewiesen.
        methods[st.name] = Method(st.name, st.cost, st.wall, st.wall_sum, False, "Teilmodelle bewiesen" if st.proven else "Teilmodelle Zeitlimit", st.routes, st.times, st.resequenced)
    if stages:
        pn = PA.post_optimize(inst, pools, tk, ty, sp, stages[-1], tl, C.WORKERS, **w)
        if pn is not None:
            methods["pn"] = Method("pn", pn.cost, pn.wall, pn.wall_sum, pn.proven, "bewiesen" if pn.proven else "Zeitlimit", pn.routes, pn.times)
    return Analysis(s, inst, pools, tk, ty, sp, methods)


# ---------------------------------------------------------------- Formate
def de(x: float, digits: int = 0) -> str:
    """Zahl im deutschen Format (Punkt als Tausendertrenner, Komma als Dezimalzeichen); nur die Zahl wird umformatiert, nie ein ganzer Satz."""
    s = f"{x:,.{digits}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def pct_over(value: float, ref: float) -> str:
    """„X % darüber“: Basis ist die Referenz (der kleinere Wert); bei Referenz 0 nicht definiert."""
    return de(100.0 * (value - ref) / ref, 0) + " %" if ref > 0 else "nicht definiert (Referenz 0)"


def is_double(value: float, ref: float) -> bool:
    """Mehr als doppelt so teuer (mit kleinem Spielraum gegen Rauschen bei kleinen Werten)."""
    return value > C.STRICT_DOUBLE * ref + C.DOUBLE_SLACK


def fahren(n: int) -> str:
    """„fährt“ oder „fahren“ nach der Zahl der Aufträge."""
    return "fährt" if n == 1 else "fahren"


def _note(a: Analysis, keys) -> str:
    unproven = [C.METHOD_LABELS[k] for k in keys if k in a.methods and not a.methods[k].proven]
    return f" Nicht bewiesen optimal (Zeitlimit erreicht): {', '.join(unproven)}." if unproven else ""


# ---------------------------------------------------------------- Verdikte (reine Funktionen: Art, Text)
def verdict_zuschnitt(a: Analysis):
    """Was kostet der Pool-Zuschnitt? Gesamtplanung mit festen Pools (G2) gegen Gesamtplanung ohne Pooling (G1)."""
    g1, g2 = a.obj("g1"), a.obj("g2")
    note = _note(a, ("g1", "g2"))
    if g1 == 0 and g2 == 0:
        return "success", f"In dieser Instanz kostet der Zuschnitt nichts: auch bei festen Pools gibt es keine Verspätung (Zielwert 0).{note}"
    if g1 == 0:
        return "warning", f"Ohne Pooling gibt es keine Verspätung, bei festen Pools kostet der Zuschnitt {de(g2)} Zielwertpunkte.{note}"
    if g2 <= g1:
        return "success", f"Feste Pools sind hier nicht schlechter als ohne Pooling: Zielwert {de(g2)} gegen {de(g1)}. Ohne Pooling ist der Wert eine obere Schranke, wenn er nicht bewiesen ist.{note}"
    if g2 <= 1.05 * g1:
        return "success", f"Feste Pools kosten hier kaum etwas: Zielwert {de(g2)} gegen {de(g1)} ohne Pooling ({pct_over(g2, g1)} darüber).{note}"
    kind = "warning" if is_double(g2, g1) else "info"
    return kind, f"Feste Pools kosten in dieser Instanz Zielwert {de(g2)} gegen {de(g1)} ohne Pooling: {pct_over(g2, g1)} darüber, das {de(g2 / g1, 1)}-Fache.{note}"


def verdict_leihen(a: Analysis):
    """Wann hilft Leihen? G3 gegen G2 und G1."""
    g1, g2, g3 = a.obj("g1"), a.obj("g2"), a.obj("g3")
    foreign = a.methods["g3"].cost.foreign
    n = a.inst.n_jobs
    note = _note(a, ("g2", "g3"))
    if foreign == 0 and g3 == g2:
        return "info", f"Leihen wird hier nicht genutzt: kein Auftrag fährt poolfremd, der Zielwert bleibt bei {de(g2)}.{note}"
    if g3 >= g2:
        return "info", f"Leihen bringt hier nichts: Zielwert {de(g3)} gegen {de(g2)} bei festen Pools ({foreign} von {n} Aufträgen poolfremd).{note}"
    gap = f", das holt {de(100.0 * (g2 - g3) / (g2 - g1), 0)} % der Lücke zur Gesamtplanung ohne Pooling zurück" if g2 > g1 else ""
    return "success", f"Leihen senkt den Zielwert von {de(g2)} auf {de(g3)} (einschließlich der Strafe), {foreign} von {n} Aufträgen {fahren(foreign)} poolfremd{gap}.{note}"


def verdict_parallel(a: Analysis):
    """Was kostet die getrennte Pool-Rechnung? p0, p1 und pn gegen G2 (nur diese eine Instanz; die Verteilung zeigt die vorgerechnete Reihe)."""
    g2, p0, p1 = a.obj("g2"), a.obj("p0"), a.obj("p1")
    note = _note(a, ("g2",))
    head = f"Getrennt gerechnet kostet der Plan {de(p0)} (nur Zeiten neu gerechnet) und {de(p1)} (eine Runde Freigabezeiten); die Gesamtplanung mit festen Pools {de(g2)}."
    if p1 == g2:
        kind, tail = "success", " In dieser Instanz gibt es mit einer Runde keinen Verlust."
    elif is_double(p1, g2):
        kind, tail = "warning", f" Nach einer Runde ist der Plan mehr als doppelt so teuer ({pct_over(p1, g2)} darüber)."
    else:
        kind, tail = "info", f" Nach einer Runde liegt der Plan {pct_over(p1, g2)} über der Gesamtplanung."
    extra = ""
    if "pn" in a.methods:
        pn = a.methods["pn"]
        extra = f" Die globale Nachoptimierung erreicht {de(pn.cost.obj)} nach {de(pn.wall, 1)} s."
    if a.methods["p0"].resequenced or a.methods["p1"].resequenced:
        extra += " Die Nachbehandlung musste die Reihenfolge je SC neu bilden (Verklemmung im zusammengesetzten Plan)."
    return kind, head + tail + extra + " Das ist eine einzelne Instanz, und das Ergebnis hängt davon ab, welchen von mehreren gleich guten Plänen jedes Pool-Modell liefert; die Verteilung über viele Instanzen steht in der vorgerechneten Reihe." + note


# ---------------------------------------------------------------- Vorgerechnete Reihe
def series_stats(records: list, key: str = "p1", ref: str = "g2") -> dict:
    """Verteilung je Instanz: Anteil gleich dem Vergleichsplan, mehr als doppelt so teuer, größter Aufschlag, Mittel beider.
    records: Liste von Wörterbüchern {Verfahren: Zielwert}."""
    n = len(records)
    equal = sum(1 for r in records if r[key] == r[ref])
    double = sum(1 for r in records if is_double(r[key], r[ref]))
    worst = max((r[key] - r[ref] for r in records), default=0)
    return dict(n=n, equal=equal, double=double, worst=worst, mean_key=sum(r[key] for r in records) / n if n else 0.0, mean_ref=sum(r[ref] for r in records) / n if n else 0.0)


def load_series(path: Path = SERIES_PATH):
    """Vorgerechnete Messreihe aus data/messreihe.json oder None, wenn die Datei fehlt."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
