# Testdaten

Erzeugt mit `python scripts/generate_testdata.py` (deterministisch, Seed 2025). Drei Quellen, drei Formate:

| Datei | Quelle | Format | Besonderheiten |
|---|---|---|---|
| `internal.db` | Interne Datenbank | SQLite, Tabelle `transactions` | Beträge als `REAL`, Zeiten UTC (`YYYY-MM-DD HH:MM:SS`), Status `completed/pending/failed/refunded`, teils unsaubere Referenzen (Großbuchstaben, Leerzeichen), eine Buchung ohne Provider-Referenz |
| `provider_a.csv` | Zahlungsdienstleister A | CSV, `;`-getrennt, UTF-8 mit BOM | deutsche Zahlen (`1.234,56`) und Daten (`03.03.2025 10:16:02`), Status `ABGESCHLOSSEN/AUSSTEHEND/FEHLGESCHLAGEN/ERSTATTET`, Leerzeile am Ende, eine unlesbare Zeile (`n/a`) |
| `provider_b.json` | Zahlungsdienstleister B | JSON | Beträge in Minor Units (`{"minor": 12345, "currency": "EUR"}`, JPY ohne Nachkommastellen), ISO-8601 mit Offset (`+02:00`) oder `Z`, Status `captured/pending/declined/refunded`, ein unbekannter Status, ein Eintrag ohne `id` |
| `expected.json` | Ground Truth | JSON | von Hand festgelegte Erwartung je Konstellation – die Tests vergleichen das Abgleichsergebnis dagegen |

## Eingebaute Konstellationen

| Konstellation | Anzahl | Erwartung |
|---|---|---|
| Saubere Treffer (inkl. USD, JPY, erstattet, fehlgeschlagen, ausstehend, unsaubere Referenzschreibweise) | 23 (+2 Originale der Duplikate) | zugeordnet, keine Abweichung |
| Betragsabweichung (Zahlendreher, +90 €, Dezimalfehler 12.000 → 1.200) | 4 | `AMOUNT_MISMATCH` |
| Statusabweichung (u. a. abgeschlossen ↔ erstattet/fehlgeschlagen/unbekannt) | 6 | `STATUS_MISMATCH` |
| Betrag **und** Status abweichend | 1 | beide Befunde, Auswirkung nur einmal gezählt |
| Währungsabweichung (EUR ↔ USD) | 1 | `CURRENCY_MISMATCH`, immer hohe Priorität |
| Nur in der Datenbank (inkl. ausstehend, ohne Referenz, unlesbare Abrechnungszeile) | 6 | `MISSING_IN_PROVIDER` |
| Nur in der Abrechnung | 3 | `MISSING_IN_DB` |
| Duplikat in Abrechnung / in Datenbank | 1 / 1 | `DUPLICATE_IN_PROVIDER` / `DUPLICATE_IN_DB` |
| Unscharfe Zuordnung (Tippfehler, fehlendes Zeichen, mit/ohne Betragsabweichung) | 3 | zugeordnet mit `REFERENCE_MISMATCH` |
| Köder: fast gleiche Referenz, aber völlig anderer Betrag | 1 Paar | darf **nicht** unscharf zugeordnet werden |

Mit `--bulk N` erzeugt der Generator zufällige Massendaten (z. B. für `scripts/benchmark.py`).
