# Preset-Abstimmung (aus `data/messreihe.json`)

Stand 16.11.2026, je Szenario 30 erzeugte Instanzen (Seeds ab 1000), Zeitlimit 10 s. Ausgewählt wird die Instanz mit bewiesener Gesamtplanung mit festen Pools (G2), deren Verhältnisse (G2/G1, G3/G1, P1/G2) am nächsten an den Medianen liegen und höchstens um den Faktor 1,5 davon abweichen, soweit es solche gibt (Ausnahme: Szenarien mit Aufschlag, siehe `tools/tune_presets.py`).

| Szenario | Seed | Ordnung G1 ≤ G3 ≤ G2 ≤ P1 und G2 ≤ Liste in … | Median G2/G1 | Median G3/G1 | P1 = G2 in … | P1 mehr als doppelt in … |
| --- | --- | --- | --- | --- | --- | --- |
| Kleiner Hafen | 1023 | 30 von 30 | 2,53 | 1,26 | 25 von 30 | 4 von 30 |
| Gute Stapelung | 1021 | 30 von 30 | 3,80 | 1,62 | 28 von 30 | 0 von 30 |
| Schlechte Stapelung | 1028 | 30 von 30 | 2,49 | 1,21 | 15 von 30 | 8 von 30 |
| Zu enge Pools | 1003 | 30 von 30 | 20,97 | 1,93 | 25 von 30 | 1 von 30 |
| Reichlich SC | 1000 | 30 von 30 | 1,00 | 1,00 | 27 von 30 | 3 von 30 |

Hinweis: Das Verhältnis wird als (a + 1) / (b + 1) gebildet, damit ein Nenner 0 (keine Verspätung) das Verhältnis nicht undefiniert macht.
