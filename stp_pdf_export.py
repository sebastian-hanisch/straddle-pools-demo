"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute sind erlaubt, aber Gedankenstrich, Pfeile, Emoji usw. lassen fpdf2 abstürzen. Deshalb läuft jeder Text durch pdf_text()."""

import time

import stp_constants as C
import stp_evaluation as ev
import stp_pools as PL

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "σ": "Sigma", "δ": "Delta", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR",
    "·": "-", "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", "±": "+-", "×": "x", "**": "",
}


def pdf_text(text) -> str:
    """Text für die Helvetica-Kernschrift: bekannte Sonderzeichen ersetzen, den Rest Latin-1-sicher machen."""
    text = str(text)
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_pdf(a: ev.Analysis, compress: bool = True) -> bytes:
    """Ergebnis der aktuellen Einstellung als PDF: Szenario, Verfahrensvergleich, Kernfragen, Hinweise zu den Annahmen."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    s = a.settings
    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def para(text, size=10):
        pdf.set_font("Helvetica", "", size)
        pdf.multi_cell(0, 5.5, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 8)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(value), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        """Beginnt einen Abschnitt auf einer neuen Seite, wenn er sonst über den Seitenumbruch liefe."""
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    line("Straddle Carrier: Pools, Abhängigkeiten und getrennte Rechnung", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    heading("Szenario")
    para(f"{a.inst.n_cranes} Kräne mit je {s.orders_per_crane} Aufträgen ({a.inst.n_orders} Aufträge), {s.n_sc} SC, Zuschnitt: {PL.STRATEGY_LABELS[s.strategy]} "
         f"({a.pools.n_pools} Pools, SC je Pool: {', '.join(str(len(a.pools.scs_of(p))) for p in range(a.pools.n_pools))}). "
         f"{s.dep_pct} % der Aufträge in Stapelpaaren, davon {s.mis_pct} % entgegen der Bedarfsreihenfolge ({a.inst.n_deps()} Abhängigkeiten, "
         f"{PL.cross_arcs(a.inst, a.pools)} zwischen Pools). Zufalls-Seed {s.seed}.")
    para(f"Zielwert = {s.w_crane} x Kranverspätung + {C.W_YARD} x Yard-Verspätung (Sekunden) + {s.penalty} je poolfremdem Auftrag. Kleiner ist besser.", 9)
    pdf.ln(2)

    heading("Verfahrensvergleich")
    rows = []
    for key in C.METHOD_KEYS:
        if key not in a.methods:
            continue
        m = a.methods[key]
        rows.append([C.METHOD_LABELS[key], ev.de(m.cost.obj), ev.de(m.cost.tard_crane), ev.de(m.cost.tard_yard), str(m.cost.foreign) if key in ("g1", "g3") else "0",
                     ev.de(m.wall, 1), m.status])
    table(["Verfahren", "Zielwert", "Kran (s)", "Yard (s)", "Fremd", "Zeit (s)", "Status"], [68, 20, 20, 20, 14, 18, 30], rows)
    pdf.ln(2)
    para("Status Zeitlimit: bestes gefundenes Ergebnis ohne Beweis, dass es optimal ist. Rechenzeit der parallelen Verfahren: längste Pool-Zeit je Durchgang.", 8)
    pdf.ln(2)

    keep_together(70)
    heading("Kernfragen")
    for title, fn in (("1. Was kostet der Pool-Zuschnitt?", ev.verdict_zuschnitt), ("2. Wann hilft Leihen?", ev.verdict_leihen), ("3. Was kostet die getrennte Pool-Rechnung?", ev.verdict_parallel)):
        pdf.set_font("Helvetica", "B", 10)
        line(title, 6)
        para(fn(a)[1], 9)
        pdf.ln(1)

    keep_together(60)
    heading("Hinweise zu den Annahmen")
    para("Die Instanzen sind erzeugt, nicht aus einem Terminal. Terminal: Manhattan-Wege mit 6 m/s, Operation 15 s, Übergabe 20 s. Die Richtzeiten sind Daten, es gibt keine "
         "Rückkopplung vom Kran auf den SC. Kranreihenfolge als Nebenbedingung, ein Blocker darf vorgezogen werden (der SC wartet am Yard). Gewichte und Strafe sind Annahmen "
         "der Demo. Keine Störungen, kein Umstapeln. Die Befunde gelten für diese Instanz und dieses Modell.", 9)
    return bytes(pdf.output())
