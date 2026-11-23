"""Konstanten: Regler-Grenzen, Vorgaben, Farben und Presets. Feste Terminalparameter stehen in stp_terminal.py."""

import os

# --- Regler: Bereich, Vorgabe ---
N_CRANES_RANGE, N_CRANES_DEFAULT = (2, 4), 4
ORDERS_PER_CRANE_RANGE, ORDERS_PER_CRANE_DEFAULT = (3, 8), 6
MAX_ORDERS = 32                                  # Kräne x Aufträge je Kran höchstens so viel (live; größere Fälle nur in der vorgerechneten Reihe)
N_SC_RANGE, N_SC_DEFAULT = (2, 10), 6
DEP_PCT_RANGE, DEP_PCT_STEP, DEP_PCT_DEFAULT = (0, 40), 5, 30
MIS_PCT_RANGE, MIS_PCT_STEP, MIS_PCT_DEFAULT = (0, 50), 5, 30
W_CRANE_RANGE, W_CRANE_DEFAULT = (1, 10), 5
PENALTY_RANGE, PENALTY_STEP, PENALTY_DEFAULT = (0, 100), 5, 30
TIME_LIMIT_RANGE, TIME_LIMIT_DEFAULT = (2, 20), 10
SEED_RANGE, SEED_DEFAULT = (0, 9999), 1023                 # = Zufalls-Seed des Presets „Kleiner Hafen“ (tools/tune_presets.py)
N_BLOCKS = 6
WORKERS = 2                                    # CP-SAT-Prozesse je Modell (Annahme: kleiner Rechner)
W_YARD = 1                                     # Gewicht der Verspätung am Yard (fest)

# Test-Obergrenze für das Zeitlimit je Modell (Sekunden), gesetzt in tests/conftest.py; ohne die Umgebungsvariable gilt der Regler.
MAX_SECONDS_ENV = "STP_MAX_SECONDS"


def time_limit(requested: float) -> float:
    cap = os.environ.get(MAX_SECONDS_ENV)
    return min(requested, float(cap)) if cap else requested


# --- Pool-Zuschnitte der Auswahl (ohne „Ein Pool“: das ist das Verfahren G1) ---
STRATEGY_KEYS = ("per_crane", "adjacent", "balanced", "coupled")
STRATEGY_DEFAULT = "adjacent"

# --- Verfahren (Reihenfolge der Anzeige) ---
METHOD_KEYS = ("list", "g1", "g2", "g3", "p0", "p1", "pn")
METHOD_LABELS = {
    "list": "Gieriges Listenverfahren",
    "g1": "Gesamtplanung ohne Pooling",
    "g2": "Gesamtplanung, Pools fest",
    "g3": "Gesamtplanung, Pools mit Leihen",
    "p0": "Parallel, nur Zeiten neu gerechnet",
    "p1": "Parallel, eine Runde Freigabezeiten",
    "pn": "Parallel + globale Nachoptimierung",
}
METHOD_SHORT = {"list": "Liste", "g1": "Gesamt<br>ohne Pools", "g2": "Gesamt<br>Pools fest", "g3": "Gesamt<br>mit Leihen", "p0": "Parallel", "p1": "Parallel<br>+ Runde", "pn": "Parallel<br>+ Nachopt."}
METHOD_DESCRIPTIONS = {
    "list": "Aufträge in Reihenfolge der Kran-Richtzeit, jeder an den SC im eigenen Pool, bei dem seine gewichtete Verspätung am kleinsten ist. Keine Suche, keine Vorausschau.",
    "g1": "Ein CP-SAT-Modell über alle Aufträge; jeder SC darf jeden Auftrag fahren (Pools spielen keine Rolle, nur die Startposition der SC bleibt die des Zuschnitts). Poolfremde Aufträge werden nur gezählt und kosten hier keine Strafe.",
    "g2": "Ein CP-SAT-Modell über alle Aufträge, alle Abhängigkeiten; jeder SC fährt nur Aufträge der Kräne seines Pools.",
    "g3": "Wie die Gesamtplanung mit festen Pools, aber ein SC darf poolfremde Aufträge übernehmen; jeder kostet die Strafe (Notlösung).",
    "p0": "Jeder Pool plant allein, ohne Abhängigkeiten zu anderen Pools. Danach werden die Zeiten mit allen Abhängigkeiten neu gerechnet; ein SC wartet am Stellplatz auf den Blocker. Das Ergebnis hängt davon ab, welchen von mehreren gleich guten Plänen jedes Pool-Modell liefert.",
    "p1": "Wie Parallel, danach rechnet jeder Pool noch einmal, mit den Fertigzeiten fremder Blocker aus dem ersten Plan als Freigaben.",
    "pn": "Das Gesamtmodell mit festen Pools, gestartet mit dem Plan der parallelen Rechnung (eine Runde), mit Zeitlimit.",
}

# --- Kurven und Texte ---
STRICT_DOUBLE = 2.0                            # „mehr als doppelt so teuer“ heißt mehr als das Doppelte plus DOUBLE_SLACK
DOUBLE_SLACK = 50

# --- Darstellung ---
METHOD_COLORS = {"list": "#8a94a3", "g1": "#2a6fb0", "g2": "#2e7d4f", "g3": "#7a3fb0", "p0": "#c77700", "p1": "#b0356a", "pn": "#1a8a8a"}
CRANE_COLORS = ("#2a6fb0", "#c77700", "#2e7d4f", "#7a3fb0")
CRANE_COLOR_NAMES = ("blau", "orange", "grün", "violett")
LATE_COLOR = "#d62728"
LINE_COLOR = "#808895"
CHART_HEIGHT = 380

# --- Presets: Einstellungen je Szenario (fehlende Regler meinen die Vorgabe) ---
_BASE = dict(n_cranes=N_CRANES_DEFAULT, orders_per_crane=ORDERS_PER_CRANE_DEFAULT, n_sc=N_SC_DEFAULT, dep_pct=DEP_PCT_DEFAULT, mis_pct=MIS_PCT_DEFAULT,
             strategy=STRATEGY_DEFAULT, w_crane=W_CRANE_DEFAULT, penalty=PENALTY_DEFAULT, time_limit=TIME_LIMIT_DEFAULT, seed=SEED_DEFAULT)
PRESETS = {
    "Kleiner Hafen": dict(_BASE, seed=1023),
    "Gute Stapelung": dict(_BASE, mis_pct=0, seed=1021),
    "Schlechte Stapelung": dict(_BASE, mis_pct=50, seed=1028),
    "Zu enge Pools": dict(_BASE, strategy="per_crane", seed=1003),
    "Reichlich SC": dict(_BASE, n_sc=10, seed=1000),
}
PRESET_HELP = {
    "Kleiner Hafen": "Vier Kräne mit je 6 Aufträgen, 6 SC in Paar-Pools, 30 % der Aufträge in Stapelpaaren, davon 30 % entgegen der Bedarfsreihenfolge gestapelt. Ein typischer Zufalls-Seed der vorgerechneten Messreihe.",
    "Gute Stapelung": "Wie der kleine Hafen, aber kein Paar entgegen der Bedarfsreihenfolge gestapelt: Abhängigkeiten kosten wenig. Ein typischer Zufalls-Seed der Messreihe.",
    "Schlechte Stapelung": "Wie der kleine Hafen, aber die Hälfte der Stapelpaare liegt entgegen der Bedarfsreihenfolge. Der Zufalls-Seed ist ein Beispiel aus den Instanzen der Messreihe, in denen die getrennte Pool-Rechnung mit einer Runde mehr als doppelt so teuer wird.",
    "Zu enge Pools": "Jeder Kran ist ein eigener Pool: kein SC kann einem anderen Kran helfen. Ein typischer Zufalls-Seed der Messreihe.",
    "Reichlich SC": "10 SC für vier Kräne: die Flotte ist so groß, dass der Pool-Zuschnitt für die Gesamtplanung nichts mehr kostet. Ein typischer Zufalls-Seed der Messreihe.",
}
