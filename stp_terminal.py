"""Feste Terminalparameter und Wege (Annahmen der Demo, an keinem Terminal gemessen).

Alle Zeiten ganzzahlig in Sekunden, alle Längen ganzzahlig in Metern. Das Terminal ist fest: Kai oben (y = 0), die Yard-Blöcke darunter,
die Kräne in festem Abstand am Kai. Straddle Carrier (SC) fahren auf Manhattan-Wegen mit konstanter Geschwindigkeit."""

SPEED = 6               # Fahrgeschwindigkeit (m/s)
SERVICE = 15            # Aufnehmen oder Absetzen am Stellplatz (s)
HAND = 20               # Übergabe am Kran (s); zugleich Mindestabstand zweier Übergaben derselben Brücke
CRANE_SPACING = 40      # Abstand zweier Kräne am Kai (m)
YARD_OFFSET = 110       # Abstand der ersten Blockreihe vom Kai (m); jeder zweite Block liegt weitere YARD_STAGGER m dahinter
YARD_STAGGER = 20
CYCLE = 75              # Takt je Kran: Richtzeit des k-ten Auftrags einer Warteschlange = LEAD + k * CYCLE (s)
LEAD = 120              # Vorlauf der ersten Richtzeit (s)


def tt(p: tuple, q: tuple) -> int:
    """Fahrzeit in ganzen Sekunden zwischen zwei Punkten (Manhattan-Weg, auf ganze Sekunden gerundet, rein ganzzahlig)."""
    dist = abs(p[0] - q[0]) + abs(p[1] - q[1])
    return (dist + SPEED // 2) // SPEED


def crane_position(c: int) -> tuple:
    """Kran c steht mittig über einem Abschnitt von CRANE_SPACING Metern am Kai."""
    return (CRANE_SPACING * c + CRANE_SPACING // 2, 0)


def block_position(b: int, n_blocks: int, n_cranes: int) -> tuple:
    """Stellplatz-Mitte des Blocks b: Blöcke gleichmäßig über die Kailänge verteilt, jede zweite Reihe weiter hinten."""
    quay = n_cranes * CRANE_SPACING
    x = (2 * b + 1) * quay // (2 * n_blocks)
    return (x, YARD_OFFSET + YARD_STAGGER * (b % 2))
