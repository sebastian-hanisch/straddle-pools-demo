"""Verdikte und Formate an von Hand gesetzten Zielwerten (DEMO-PLAYBOOK §12): jede Schwelle und jede Zahl im Text steht hier.

Ein Verdikt ist eine reine Funktion (Art, Text) auf einer Analyse; die Analyse wird hier aus festen Zielwerten gebaut, nicht gerechnet."""

import pytest

import stp_evaluation as ev
import stp_instance as I
import stp_pools as PL
import stp_timing as M


def fake(g1=0, g2=0, g3=0, p0=0, p1=0, pn=None, foreign=0, proven=True, reseq=False, n_orders_cranes=(2, 3), pn_wall=2.0):
    inst = I.make_instance(1, n_cranes=n_orders_cranes[0], n_per_crane=n_orders_cranes[1])
    pools = PL.make_pools(inst, 2, "per_crane")

    def meth(key, obj, f=0, ok=proven, wall=1.0, rs=False):
        return ev.Method(key, M.Cost(obj, 0, 0, f), wall, wall, ok, "bewiesen" if ok else "Zeitlimit", (), (), rs)

    methods = {"g1": meth("g1", g1), "g2": meth("g2", g2), "g3": meth("g3", g3, foreign), "p0": meth("p0", p0, rs=reseq), "p1": meth("p1", p1)}
    if pn is not None:
        methods["pn"] = meth("pn", pn, wall=pn_wall)
    return ev.Analysis(ev.Settings(), inst, pools, (), (), (), methods)


def test_zahlenformat_deutsch():
    assert ev.de(1234.5, 1) == "1.234,5" and ev.de(0) == "0" and ev.de(1234567) == "1.234.567" and ev.de(-12.34, 1) == "-12,3"


def test_prozent_darueber_mit_basis_und_nullreferenz():
    assert ev.pct_over(150, 100) == "50 %" and ev.pct_over(100, 100) == "0 %" and ev.pct_over(2100, 100) == "2.000 %"
    assert "nicht definiert" in ev.pct_over(5, 0)


def test_mehr_als_doppelt_hat_einen_spielraum_von_50():
    assert not ev.is_double(250, 100) and ev.is_double(251, 100)
    assert not ev.is_double(50, 0) and ev.is_double(51, 0)


def test_fahren_singular_und_plural():
    assert ev.fahren(1) == "fährt" and ev.fahren(0) == "fahren" and ev.fahren(2) == "fahren"


def test_zuschnitt_ohne_verspaetung_kostet_nichts():
    kind, text = ev.verdict_zuschnitt(fake(0, 0))
    assert kind == "success" and "kostet der Zuschnitt nichts" in text and "Zielwert 0" in text


def test_zuschnitt_ohne_pooling_keine_verspaetung_bei_festen_pools_schon():
    kind, text = ev.verdict_zuschnitt(fake(0, 130))
    assert kind == "warning" and "Ohne Pooling gibt es keine Verspätung" in text and "130 Zielwertpunkte" in text


def test_zuschnitt_unbewiesener_wert_ohne_pooling_ueber_dem_der_festen_pools():
    kind, text = ev.verdict_zuschnitt(fake(200, 100, proven=False))
    assert kind == "success" and "nicht schlechter als ohne Pooling: Zielwert 100 gegen 200" in text and "darüber" not in text and "Nicht bewiesen optimal" in text
    kind, text = ev.verdict_zuschnitt(fake(100, 100))
    assert kind == "success" and "nicht schlechter" in text


def test_zuschnitt_schwelle_ist_inklusive_bei_fuenf_prozent():
    kind, text = ev.verdict_zuschnitt(fake(100, 105))
    assert kind == "success" and "Zielwert 105 gegen 100" in text and "5 % darüber" in text
    kind, text = ev.verdict_zuschnitt(fake(100, 106))
    assert kind == "info" and "6 % darüber" in text and "1,1-Fache" in text


def test_zuschnitt_info_und_warnung_an_der_doppelt_grenze():
    kind, text = ev.verdict_zuschnitt(fake(100, 250))                      # 250 ist nicht mehr als 2 * 100 + 50
    assert kind == "info" and "150 % darüber" in text and "2,5-Fache" in text
    kind, text = ev.verdict_zuschnitt(fake(100, 251))
    assert kind == "warning"
    kind, text = ev.verdict_zuschnitt(fake(10, 2100))
    assert kind == "warning" and "20.900 % darüber" in text and "210,0-Fache" in text


def test_leihen_nicht_genutzt_bringt_nichts_und_hilft():
    kind, text = ev.verdict_leihen(fake(10, 90, 90, foreign=0))
    assert kind == "info" and "nicht genutzt" in text and "bleibt bei 90" in text
    kind, text = ev.verdict_leihen(fake(10, 90, 95, foreign=3, n_orders_cranes=(2, 3)))
    assert kind == "info" and "bringt hier nichts" in text and "95 gegen 90" in text and "3 von 6 Aufträgen" in text
    kind, text = ev.verdict_leihen(fake(10, 110, 60, foreign=2))
    assert kind == "success" and "von 110 auf 60" in text and "2 von 6 Aufträgen fahren poolfremd" in text and "50 % der Lücke" in text


def test_leihen_singular_und_ohne_luecke():
    kind, text = ev.verdict_leihen(fake(10, 110, 60, foreign=1))
    assert "1 von 6 Aufträgen fährt poolfremd" in text
    kind, text = ev.verdict_leihen(fake(100, 100, 50, foreign=1))           # keine Lücke zur Gesamtplanung ohne Pooling: kein Satz über die Lücke
    assert kind == "success" and "Lücke" not in text


def test_parallel_kein_verlust_aufschlag_und_doppelt():
    kind, text = ev.verdict_parallel(fake(g2=100, p0=100, p1=100))
    assert kind == "success" and "kostet der Plan 100 (nur Zeiten neu gerechnet) und 100 (eine Runde" in text and "keinen Verlust" in text
    kind, text = ev.verdict_parallel(fake(g2=100, p0=300, p1=180))
    assert kind == "info" and "80 % über" in text and "kostet der Plan 300" in text
    kind, text = ev.verdict_parallel(fake(g2=100, p0=900, p1=400))
    assert kind == "warning" and "mehr als doppelt so teuer (300 % darüber)" in text
    assert "einzelne Instanz" in text and "gleich guten Plänen" in text


def test_parallel_nennt_nachoptimierung_und_neu_sequenzierung_und_unbewiesenes():
    kind, text = ev.verdict_parallel(fake(g2=100, p0=900, p1=400, pn=100, pn_wall=2.34, reseq=True))
    assert "Nachoptimierung erreicht 100 nach 2,3 s" in text and "Reihenfolge je SC neu bilden" in text
    kind, text = ev.verdict_parallel(fake(g2=100, p0=100, p1=100, proven=False))
    assert "Nicht bewiesen optimal" in text and "Gesamtplanung, Pools fest" in text


def test_ohne_nachoptimierung_kein_satz_dazu():
    assert "Nachoptimierung" not in ev.verdict_parallel(fake(g2=100, p0=100, p1=100))[1]


def test_serienstatistik_von_hand():
    recs = [dict(g2=100, p1=100), dict(g2=100, p1=400), dict(g2=100, p1=150), dict(g2=0, p1=60)]
    s = ev.series_stats(recs, "p1")
    assert s["n"] == 4 and s["equal"] == 1 and s["double"] == 2 and s["worst"] == 300          # 400 > 250 und 60 > 50
    assert s["mean_key"] == pytest.approx(177.5) and s["mean_ref"] == pytest.approx(75.0)
    assert ev.series_stats([], "p1")["n"] == 0
