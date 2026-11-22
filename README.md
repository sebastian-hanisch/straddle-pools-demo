# Straddle Carrier: Pools, Abhängigkeiten und getrennte Rechnung – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-straddle-pools-demo.streamlit.app/)**

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`). Straddle Carrier (SC) fahren Container zwischen Kran und Stapelplatz im Yard eines Containerterminals.
Jeder Kran hat eine feste Warteschlange von Aufträgen mit Richtzeiten; die SC sind in **Pools** festen Kränen zugeordnet. Die Demo plant dieselbe erzeugte Instanz mit sieben Verfahren und beantwortet drei Fragen:
Was kostet der Pool-Zuschnitt, wann hilft es, dass ein SC einem fremden Pool aushilft („Leihen“), und was kostet es, die Pools **getrennt und gleichzeitig** zu rechnen, wenn Aufträge verschiedener Pools voneinander abhängen.

## Warum dieses Problem

Abhängigkeiten entstehen im Yard: Liegt der Container für Kran 2 über dem Container für Kran 1, muss der obere zuerst bewegt werden, obwohl beide zu verschiedenen Pools gehören können. Wer die Pools getrennt plant (zum Beispiel, um Rechenzeit zu sparen),
kennt diese Kopplung nicht und muss sie hinterher behandeln. Die Frage der Demo: Wie groß ist der Preis dafür, und in welchen Fällen entsteht er?

## Modell

Kurz (vollständig im Expander „📐 Mathematische Formulierung“ der App, Annahmen im Expander „🚧 Wo die Annahmen enden“):

- **Terminal (Annahmen, an keinem Terminal gemessen):** Kai oben, Yard-Blöcke darunter, Manhattan-Wege mit 6 m/s auf ganze Sekunden gerundet, Aufnehmen oder Absetzen 15 s, Übergabe am Kran 20 s.
- **Aufträge:** Laden (vom Stellplatz zum Kran) oder Löschen (vom Kran zum Stellplatz), je Kran in fester Reihenfolge. Die Richtzeit am Kran ist 120 s + 75 s je Position der Warteschlange (der erste Auftrag hat Position 0); die am Yard ist beim Laden die Kranzeit minus Fahrt minus Aufnahme, beim Löschen die Kranzeit plus Übergabe plus Fahrt.
- **Abhängigkeiten:** Paare von Aufträgen gleicher Art an verschiedenen Kränen im selben Stapel; die Stellplatz-Operation des einen beginnt erst, wenn die des anderen beendet ist. Der Anteil der Aufträge in Paaren (ein Paar hat zwei Aufträge; bei 24 Aufträgen und 30 % sind das 7,2 Aufträge, gebildet werden auf ganze Paare gerundet 4 Paare, also 8 Aufträge) und der Anteil der Paare, bei denen der Auftrag, der am Stellplatz zuerst erledigt sein muss, in seiner Warteschlange später dran ist („gegen die Bedarfsreihenfolge gestapelt“), sind Regler.
- **Zielwert:** 5 · Kranverspätung + 1 · Yard-Verspätung (Summe über Aufträge, Sekunden) + 30 je poolfremdem Auftrag; Gewichte und Strafe sind Annahmen der Demo und Regler; die Messreihe rechnet mit den Voreinstellungen 5 : 1 : 30. Kleiner ist besser.
- **Nebenbedingungen:** Kranreihenfolge (Übergaben an einem Kran in Warteschlangenreihenfolge, mindestens 20 s Abstand). Ein Blocker darf vorgezogen werden; der SC wartet dann am Yard. Ein Ladeauftrag darf früher als seine Richtzeit am Kran sein (der SC wartet dort); das kostet nichts, Verspätung zählt nur nach der Richtzeit. Beim Löschen übernimmt der SC den Container frühestens zur Richtzeit.
- **Nicht im Modell:** Störungen, Fahrzeitstreuung, Umstapeln, Einbahnregeln und Staus im Yard, Rückkopplung vom Kran auf den SC (die Richtzeiten sind Daten).

## Methodik

Alle Verfahren planen dieselbe Instanz; ein „Plan“ ist die Reihenfolge der Aufträge je SC, die Zeiten rechnet `stp_timing.py` als früheste Lösung aller Zeitbedingungen.

| Verfahren | Beschreibung |
|---|---|
| Gieriges Listenverfahren | Aufträge nach Kran-Richtzeit, jeder an den SC im eigenen Pool mit der kleinsten gewichteten Verspätung. Keine Suche. |
| Gesamtplanung ohne Pooling (G1) | CP-SAT-Modell über alle Aufträge, jeder SC darf jeden Auftrag fahren (Startpositionen der SC wie beim gewählten Zuschnitt). Poolfremde Aufträge werden nur gezählt und kosten hier keine Strafe. |
| Gesamtplanung, Pools fest (G2) | Dasselbe Modell, ein SC fährt nur Aufträge der Kräne seines Pools. |
| Gesamtplanung, Pools mit Leihen (G3) | Wie G2, aber poolfremde Aufträge sind erlaubt und kosten die Strafe. |
| Parallel, nur Zeiten neu gerechnet (P0) | Jeder Pool plant allein ohne Abhängigkeiten zu anderen Pools; danach werden die Zeiten mit allen Abhängigkeiten neu gerechnet (der SC wartet auf den Blocker), bei einer Verklemmung wird die Reihenfolge je SC nach geplanter Startzeit neu gebildet. Das Ergebnis hängt davon ab, welchen von mehreren gleich guten Plänen jedes Pool-Modell liefert (siehe „Wiederholbarkeit“). |
| Parallel + Runde (P1) | Wie P0, danach rechnet jeder Pool noch einmal, mit den Fertigzeiten fremder Blocker aus dem Plan von P0 als Freigaben. |
| Parallel + globale Nachoptimierung (PN) | G2, gestartet mit dem Plan von P1, mit Zeitlimit. |

Die Pool-Zuschnitte: Pool je Kran, benachbarte Paare, Paare nach ausgeglichener Arbeitslast, Paare mit den meisten gemeinsamen Abhängigkeiten. Die SC-Zahl je Pool folgt der Arbeitslast, jeder Pool hat mindestens einen SC.
Die Rechenzeit der parallelen Verfahren ist die längste Pool-Zeit je Durchgang (angenommen: alle Pools rechnen gleichzeitig; gemessen wird nacheinander).

## Befunde (gemessen; Deutungen sind als solche gekennzeichnet)

Alle Zahlen stammen aus der vorgerechneten Messreihe (`data/messreihe.json`, Werkzeug `tools/messreihe.py`): je Szenario **30 erzeugte Instanzen** mit 24 Aufträgen (4 Kräne, 6 Aufträge je Kran, Zufalls-Seeds 1000 bis 1029), 6 SC (im Szenario „Reichlich SC“ 10), Paar-Pools (im Szenario „Zu enge Pools“ ein Pool je Kran), Zeitlimit 10 s je Modell, 2 CP-SAT-Prozesse, gerechnet am 16.11.2026.
„Gleich“ heißt: Zielwert gleich dem der Gesamtplanung mit festen Pools (G2). „Mehr als doppelt“ heißt: mehr als das Doppelte von G2 plus 50. Szenarien: „Kleiner Hafen“ (30 % der Aufträge in Stapelpaaren, davon 30 % gegen die Bedarfsreihenfolge), „Gute Stapelung“ (0 % gegen die Reihenfolge),
„Schlechte Stapelung“ (50 %), „Zu enge Pools“, „Reichlich SC“. Verhältnisse sind, wenn nicht anders gesagt, der Median der Verhältnisse je Instanz, gebildet als (a + 1) / (b + 1), damit ein Zielwert 0 nicht stört. Mittelwerte stehen nur neben der Verteilung (Zahl der gleichen und der mehr als doppelten Instanzen) oder ausdrücklich als Mittel gekennzeichnet.

| Frage | Befund (Voraussetzung) | Beleg |
|---|---|---|
| Was kostet der Pool-Zuschnitt? | Kleiner Hafen: Gesamtplanung mit festen Pools kostet im Median das 2,53-Fache der Gesamtplanung ohne Pooling, mit Leihen das 1,26-Fache (Spanne des Verhältnisses fest zu ohne Pooling je Instanz 1,0 bis 283). Das Modell ohne Pooling war auf diesem Rechner (Zeitlimit 10 s) in 17 von 30 Instanzen bewiesen optimal, mit Leihen in 20; ist der Wert ohne Pooling (der Nenner) nicht bewiesen, ist er eine obere Schranke und das wahre Verhältnis fest zu ohne Pooling eher größer. | `test_claims.py::test_zuschnitt` |
| Wie stark wirkt ein zu enger Zuschnitt? | Pool je Kran: Median 20,97-fach bei festen Pools, 1,93-fach mit Leihen (30 Instanzen; Spanne des Verhältnisses fest zu ohne Pooling 3,5 bis 6.545, weil ohne Pooling oft kaum Verspätung bleibt). | `test_claims.py::test_zuschnitt` |
| Wann spielt der Zuschnitt keine Rolle? | Reichlich SC (10 SC, vier Kräne): Gesamtplanung ohne Pooling, mit festen Pools und mit Leihen haben in 30 von 30 Instanzen denselben Zielwert. | `test_claims.py::test_reichlich_sc` |
| Ist die getrennte Rechnung verlustfrei? | Im gespeicherten Lauf (die Zahlen schwanken zwischen Läufen um wenige Instanzen, siehe „Wiederholbarkeit“) ist Parallel + Runde in Kleiner Hafen in 25 von 30 Instanzen gleich G2 und in 4 von 30 mehr als doppelt so teuer (größter Aufschlag 12.172 Zielwertpunkte); Gute Stapelung 28 und 0 von 30; Schlechte Stapelung 15 und 8 von 30 (größter Aufschlag 13.526); Zu enge Pools 25 und 1 von 30; Reichlich SC 27 und 3 von 30. | `test_claims.py::test_parallel_verteilung` |
| Und ohne die Runde? | Parallel, nur Zeiten neu gerechnet (P0) ist in Kleiner Hafen in 12 von 30 Instanzen gleich G2 und in 15 von 30 mehr als doppelt so teuer; Schlechte Stapelung 7 und 22 von 30. | `test_claims.py::test_parallel_verteilung` |
| Das Mittel täuscht. | Kleiner Hafen: Mittel von Parallel + Runde 1.540 gegen 751 für G2, aber in 25 von 30 Instanzen gleich; das Mittel wird von wenigen Instanzen bestimmt. | `test_claims.py::test_parallel_verteilung` |
| Repariert die globale Nachoptimierung? | PN (G2 mit dem Plan von P1 als Startlösung) erreicht in allen fünf Szenarien in 30 von 30 Instanzen den Zielwert von G2; G2 ist dabei in 25 bis 30 von 30 Instanzen je Szenario bewiesen optimal, bei den übrigen sagt die Gleichheit nichts über das Optimum. | `test_claims.py::test_nachoptimierung` |
| Spart die parallele Rechnung Zeit? | Kleiner Hafen, 24 Aufträge, im Median: Parallel + Runde 0,4 s, G2 0,5 s, PN 1,0 s (im Mittel 0,6 s, 1,9 s, 2,2 s). Die Rechenzeit von G2 ist schief verteilt: in 17 von 30 Instanzen unter 0,5 s, in 6 mehr als 2 s, in 2 das Zeitlimit; das Mittel ohne diese 2 Instanzen ist 1,3 s. Der Unterschied im Median ist klein; die reparierte Variante (PN) braucht mehr als die Gesamtplanung. Parallele Rechenzeit = längste Pool-Zeit (Annahme gleichzeitiger Pools), Rechner mit 2 Prozessen. | `test_claims.py::test_rechenzeit` |
| Wie ist es bei großen Instanzen? | 84 Aufträge (6 Kräne mit je 14 Aufträgen, 10 SC, Paar-Pools, sonst die Voreinstellungen von Kleiner Hafen, 3 Instanzen, Zeitlimit 15 s): kein Gesamtmodell bewiesen. G2 im Mittel 5.862; das Modell ohne Pooling (Mittel 13.488) und das mit Leihen verbesserten den gierigen Startplan in keiner Instanz, nur G2 tat es. Parallel + Runde liegt je Instanz beim 1,72- bis 5,74-Fachen von G2, PN beim 0,98- bis 1,08-Fachen (Verhältnis der Mittel 3,59 und 1,04; G2 unbewiesen). | `test_claims.py::test_grosse_instanzen` |
| Reicht die gierige Regel nach Richtzeit? | Kleiner Hafen: Das gierige Verfahren kostet im Median das 3,02-Fache von G2. | `test_claims.py::test_zuschnitt` |

**Wie lesen:** Die Aussagen gelten für diese erzeugten Instanzen, diese Gewichte und diese Nachbehandlung; sie sagen nichts über andere Nachbehandlungen der Abhängigkeiten und nichts über echte Terminals.

### Wiederholbarkeit

Die parallelen Verfahren hängen davon ab, welchen von mehreren gleich guten Plänen jedes Pool-Modell liefert. Auch wenn jedes Pool-Modell bewiesen optimal ist (in 30 von 30 Instanzen beider Szenarien), kann ein anderer Zufalls-Seed des Lösers (1, 2 und 3, ein CP-SAT-Prozess; `tools/wiederholbarkeit.py`, `data/wiederholbarkeit.json`) den Zielwert ändern: In Kleiner Hafen ändert sich P0 in 17 von 30 Instanzen und P1 in 4, in Schlechte Stapelung P0 in 20 und P1 in 13.
Parallel + Runde ist dabei in Kleiner Hafen in 24 von 30 Instanzen gleich G2 und in 4 von 30 mehr als doppelt so teuer (in allen drei Läufen), in Schlechte Stapelung in 13 bis 15 gleich und in 8 mehr als doppelt; P0 ist in Kleiner Hafen in 11 bis 12 gleich und in 13 bis 16 mehr als doppelt, in Schlechte Stapelung in 6 bis 7 gleich und in 19 bis 23 mehr als doppelt.
Der größte Aufschlag von Parallel + Runde in Schlechte Stapelung liegt in diesen Läufen zwischen 20.729 und 27.926 (im gespeicherten Lauf 13.526): eine Größenordnung, keine feste Zahl. Verglichen wird mit dem gespeicherten Wert von G2. Die Aussage über die Verteilung (ein Teil der Instanzen gleich, ein anderer Teil sehr teuer) bleibt in allen Läufen bestehen; die einzelnen Zählungen schwanken um wenige Instanzen.


## Ehrliche Grenzen

- **Erzeugte Instanzen:** Aufträge, Stellplätze und Stapelpaare kommen aus einem Zufallsgenerator (Zufalls-Seed), nicht aus einem Terminal. Die Zahlen können sich bei echten Daten ändern.
- **Annahmen der Demo:** Gewichte (5 : 1 : 30), Richtzeiten, Wege, Zeiten und die Regel „ein Blocker darf vorgezogen werden“ sind Setzungen. Die Rangfolge der Verfahren kann an den Gewichten hängen (nicht untersucht).
- **Rechenleistung:** Die Gesamtmodelle laufen mit 2 CP-SAT-Prozessen und dem eingestellten Zeitlimit; Werte ohne Beweis können sich zwischen Läufen und Rechnern unterscheiden. Auch bewiesene Pool-Modelle haben oft mehrere gleich gute Lösungen; P0 und P1 hängen davon ab, welche der Löser liefert (siehe „Wiederholbarkeit“). Die parallele Rechenzeit ist eine Annahme (längste Pool-Zeit), gemessen wird nacheinander.
- **Eine Nachbehandlung:** Getestet ist eine einfache Nachbehandlung (Zeiten neu rechnen, eine Runde Freigabezeiten, optional Nachoptimierung). Andere Verfahren zur Behandlung der Abhängigkeiten sind nicht geprüft.
- **Stichprobe:** 30 Instanzen je Szenario, für die großen Fälle 4 Instanzen mit 48 und 3 mit 84 Aufträgen. Die großen Fälle zeigen eine Tendenz, keine Verteilung.
- **Preset-Seeds:** Die Zufalls-Seeds der Schnellstart-Szenarien sind aus der Messreihe gewählt: die Instanz mit bewiesener Gesamtplanung mit festen Pools, deren Verhältnisse G2/G1 und G3/G1 am nächsten an den Medianen des Szenarios liegen (bei „Schlechte Stapelung“ unter den Instanzen mit Aufschlag von Parallel + Runde; dort ist der Aufschlag ein Beispiel, kein Typfall). Einzelheiten und Abweichungen vom Median: `tools/PRESET_SWEEP.md`.

## Verifikation

- **Orakel Zeitrechnung:** `stp_timing.evaluate_plan` (kleinste Lösung eines Zeitbedingungssystems) gegen eine unabhängige ereignisdiskrete Simulation (`tests/test_oracle_timing.py`); beim Anlegen im Scratch-Lauf (nicht im Repo) 2000 Zufallspläne, zulässige und verklemmte, ohne Abweichung; drei absichtlich verstümmelte Auswerter wichen darin in 608 bis 1456 Fällen ab.
- **Orakel Optimum:** Das bewiesene Optimum des CP-SAT-Modells gegen Aufzählung aller Pläne auf Mini-Instanzen, bewertet mit der ereignisdiskreten Simulation (`tests/test_oracle_model.py`).
- **Eigenschaften (für bewiesene Optima; bei Zeitlimit nicht garantiert):** G1 ≤ G3 ≤ G2 ≤ P0, P1 und Listenverfahren; PN gleich G2, wenn bewiesen; ohne Abhängigkeiten zwischen Pools P0 gleich G2 (`tests/test_oracle_model.py`, `tests/test_parallel.py`, `tests/test_series.py`).
- **Kern:** Zufallsgenerator gegen veröffentlichte Referenzwerte, Instanzgenerator, Pool-Zuschnitte gegen Aufzählung aller Zerlegungen, Neu-Sequenzierung auf 120 Zufallsfällen.
- **Zahlen:** die Zahlen der Tabelle „Befunde“ gegen die gespeicherte Messreihe in `tests/test_claims.py`; die gespeicherte Reihe in `tests/test_series.py`; die Wiederholbarkeit in `tests/test_wiederholbarkeit.py`; die Schnellstart-Szenarien live in `tests/test_preset_stories.py`.
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jeder Regler an den Grenzen), Layout (Schnellstart oben in der Seitenleiste, aktives Szenario hervorgehoben), PDF-Export, Footer, Laufzeit-Importe.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-App |
| `stp_constants.py` | Regler-Grenzen, Verfahren und Beschriftungen, Farben, Schnellstart-Szenarien |
| `stp_terminal.py` | feste Terminalparameter, ganzzahlige Wege |
| `stp_rng.py` | SplitMix64 (gleiche Zufalls-Seeds auf jeder Plattform) |
| `stp_instance.py` | Instanzgenerator, Zeitkreis-Prüfung |
| `stp_timing.py` | Zeitrechnung eines Plans, Richtzeiten, Zielwert |
| `stp_pools.py` | Pool-Zuschnitte, Kopplungsmatrix |
| `stp_heuristic.py` | gieriges Listenverfahren |
| `stp_model.py` | CP-SAT-Modell |
| `stp_parallel.py` | parallele Pool-Rechnung, Nachbehandlung, Nachoptimierung |
| `stp_evaluation.py` | alle Verfahren auf einer Instanz, Verdikte, Statistik der Messreihe |
| `stp_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `stp_pdf_export.py` | PDF-Export |
| `stp_presets.py`, `stp_layout.py` | Permalink, Schnellstart, fester Kopf |
| `data/messreihe.json`, `data/wiederholbarkeit.json` | vorgerechnete Messreihe; P0 und P1 mit drei Zufalls-Seeds des Lösers |
| `tools/messreihe.py`, `tools/wiederholbarkeit.py`, `tools/tune_presets.py`, `tools/series_report.py` | Messreihe, Wiederholbarkeit, Auswahl der Zufalls-Seeds der Schnellstart-Szenarien, Kennzahlen; `tools/PRESET_SWEEP.md` |
| `tests/` | Tests (siehe Verifikation) |
| `.github/workflows/tests.yml`, `requirements*.txt`, `.streamlit/config.toml` | CI, Laufzeit-Bibliotheken, Einstellungen |

## Bewusst nicht umgesetzt

- Echte Terminaldaten, Störungen und Fahrzeitstreuung, Umstapeln, Fahrwegenetz mit Einbahnen und Staus.
- Rückkopplung vom Kran auf den SC (ein Kran, der wartet, verschiebt keine späteren Richtzeiten).
- Andere Nachbehandlungen der Abhängigkeiten (zum Beispiel mehrere Runden mit Fristen oder ein grober Gesamtplan als Schnittstelle). In der Messreihe wird nur eine Runde gerechnet; in Vormessungen (nicht im Repo) änderte sich in einem Szenario nach der zweiten Runde nichts mehr, in einem anderen brachte eine dritte noch etwas.
- Gleiche Rechenleistung für Gesamtplanung und parallele Rechnung (die Gesamtmodelle laufen mit 2 Prozessen, die Pools nacheinander).

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, OR-Tools (CP-SAT) und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Hafenlogistik optimieren](https://sebastianhanisch.net/hafenlogistik-optimierung.html).
