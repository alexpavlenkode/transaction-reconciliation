# Testdaten

Erzeugt mit `python scripts/generate_testdata.py` (deterministisch, Seed 2025). Drei Quellen, drei Formate.
Stichtag der Testdaten: **2025-04-01 00:00 UTC**, Frist 3 Tage (steht auch in `expected.json`).

| Datei | Quelle | Format | Besonderheiten |
|---|---|---|---|
| `internal.db` | Interne Datenbank | SQLite, Tabelle `transactions` | Beträge als **INTEGER Minor Units** (`amount_minor`), Zeiten UTC (`YYYY-MM-DD HH:MM:SS`), Status `completed/pending/failed/refunded`, teils unsaubere Referenzen (Groß-/Kleinschreibung, Leerzeichen), eine Buchung ohne Provider-Referenz |
| `provider_a.csv` | Zahlungsdienstleister A | CSV, `;`-getrennt, UTF-8 mit BOM | deutsche Zahlen (`1.234,56`) und Daten (`03.03.2025 10:16:02`, Spalte `Zeitstempel (UTC)`), Status `ABGESCHLOSSEN/AUSSTEHEND/FEHLGESCHLAGEN/ERSTATTET`, Leerzeile am Ende, eine unlesbare Zeile (`n/a`) |
| `provider_b.json` | Zahlungsdienstleister B | JSON | Beträge in Minor Units (`{"minor": 12345, "currency": "EUR"}`, JPY ohne Nachkommastellen), ISO-8601 mit Offset (`+02:00`) oder `Z`, Status `captured/pending/declined/refunded`, ein unbekannter Status, ein Eintrag ohne `id` |
| `expected.json` | Ground Truth | JSON | von Hand festgelegte Erwartung je Konstellation (Befunde, berechnete Auswirkung, betroffener Betrag, Sicherheit, Schwere) – die Tests vergleichen das Abgleichsergebnis dagegen |

## Eingebaute Konstellationen

| Konstellation | Anzahl | Erwartung |
|---|---|---|
| Saubere Treffer (inkl. USD, JPY, erstattet, fehlgeschlagen, ausstehend, unsaubere Schreibweise der Referenz) | 23 (+3 Originale mehrfacher Einträge) | zugeordnet, keine Abweichung |
| Betragsabweichung (Zahlendreher, +90 €, Dezimalfehler 12.000 → 1.200, 75,50 → 57,50) | 4 | `AMOUNT_MISMATCH`, Auswirkung berechnet |
| Statusabweichung (u. a. abgeschlossen ↔ erstattet/fehlgeschlagen; ausstehend ↔ fehlgeschlagen = ±0) | 5 | `STATUS_MISMATCH`, Auswirkung berechnet |
| Status **unbekannt** (`chargeback_initiated`) | 1 | `STATUS_MISMATCH`, Auswirkung **nicht bestimmbar** (nicht „0“), betroffen 330 € |
| Betrag **und** Status abweichend | 1 | beide Befunde, Auswirkung nur einmal gezählt |
| Währungsabweichung (EUR ↔ USD) | 1 | `CURRENCY_MISMATCH`, immer hoch, Auswirkung nicht bestimmbar (beide Beträge ausgewiesen) |
| Nur in der Datenbank, Frist abgelaufen (inkl. ausstehend, ohne Referenz; bei B vorläufig, weil B eine Zeile ohne ID enthält) | 5 | `MISSING_IN_PROVIDER`, mindestens mittel |
| Abrechnungszeile unlesbar, ID aber lesbar | 1 | `SOURCE_ROW_UNREADABLE` (**nicht** „fehlt“), nicht bestimmbar |
| Noch innerhalb der Frist (Buchung 31.03., Stichtag 01.04.) | 1 | `NOT_YET_DUE`, niedrig |
| Nur in der Abrechnung | 3 | `MISSING_IN_DB` |
| Mehrfach in der Abrechnung / in der Datenbank | 1 / 1 | `DUPLICATE_*`, nicht bestimmbar, betroffener Betrag |
| Mehrfach in der Abrechnung, Schreibweise verschieden (`ATX-1` / `atx1`) | 1 | `DUPLICATE_IN_PROVIDER` + `ID_COLLISION` |
| Unscharfe Zuordnung (Tippfehler, fehlendes Zeichen, mit/ohne Betragsabweichung) | 3 | zugeordnet mit `REFERENCE_MISMATCH` |
| Köder: fast gleiche Referenz, aber völlig anderer Betrag | 1 Paar | darf **nicht** unscharf zugeordnet werden |

Von Hand nachgerechnet: berechnete Nettoauswirkung **−16.583,91 EUR**, nicht bestimmbare Fälle zusammen 1.565,00 EUR
und 200,00 USD betroffener Betrag.

Mit `--bulk N` erzeugt der Generator zufällige Massendaten (z. B. für `scripts/benchmark.py`).
