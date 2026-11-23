"""PDF-Export: erzeugt ein gültiges PDF mit den Abschnitten und Zahlen, übersteht Sonderzeichen, bricht nicht mitten in einer Tabelle um."""

import re

import stp_evaluation as ev
import stp_pdf_export as X


def _analyse():
    return ev.analyse(ev.Settings(n_cranes=3, orders_per_crane=3, n_sc=4, dep_pct=40, mis_pct=40, time_limit=20, seed=2))


def _texte(pdf_bytes) -> str:
    """Alle Textstücke (Tj-Operatoren) eines unkomprimierten PDFs, durch Leerzeichen getrennt."""
    return " ".join(t.decode("latin-1") for t in re.findall(rb"\((.*?)\) Tj", pdf_bytes, flags=re.S))


def test_pdf_ist_gueltig_und_enthaelt_die_abschnitte_und_zahlen():
    a = _analyse()
    data = X.generate_pdf(a, compress=False)
    assert data.startswith(b"%PDF") and data.rstrip().endswith(b"%%EOF")
    text = _texte(data)
    for erwartet in ("Szenario", "Verfahrensvergleich", "Kernfragen", "Hinweise zu den Annahmen", "Gesamtplanung ohne Pooling"):
        assert erwartet in text, erwartet
    for key, m in a.methods.items():
        assert ev.de(m.cost.obj) in text, key
    assert f"Zufalls-Seed {a.settings.seed}" in text


def test_pdf_enthaelt_die_texte_der_drei_verdikte():
    a = _analyse()
    text = _texte(X.generate_pdf(a, compress=False))
    for fn in (ev.verdict_zuschnitt, ev.verdict_leihen, ev.verdict_parallel):
        anfang = X.pdf_text(fn(a)[1])[:25]
        assert anfang in text, anfang


def test_sonderzeichen_werden_latin1_sicher():
    assert X.pdf_text("Zielwert – 5 · Kran → Yard ≥ 3 ± 1 „x“") == 'Zielwert - 5 - Kran -> Yard >= 3 +- 1 "x"'
    assert X.pdf_text("Äpfel, Öl, Übung, ß") == "Äpfel, Öl, Übung, ß"
    assert X.pdf_text("😀") == "?"
    assert X.pdf_text("**fett**") == "fett"


def test_komprimiert_und_unkomprimiert_gleiche_seitenzahl():
    a = _analyse()
    n1 = len(re.findall(rb"/Type /Page\b", X.generate_pdf(a, compress=False)))
    n2 = len(re.findall(rb"/Type /Page\b", X.generate_pdf(a, compress=True)))
    assert n1 == n2 and 1 <= n1 <= 3
