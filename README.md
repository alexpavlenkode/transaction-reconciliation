# Transaktionsabgleich

[![CI](https://github.com/alexpavlenkode/transaction-reconciliation/actions/workflows/ci.yml/badge.svg)](https://github.com/alexpavlenkode/transaction-reconciliation/actions/workflows/ci.yml)

Gleicht die **interne Buchungsdatenbank** mit den Abrechnungen von **Zahlungsdienstleister A** (CSV) und
**Zahlungsdienstleister B** (JSON) ab, erkennt fehlende Einträge sowie Betrags-, Status- und Währungsabweichungen,
berechnet die **finanziellen Auswirkungen** und erzeugt einen **priorisierten, handlungsorientierten Bericht**
(Markdown, HTML-Dashboard, JSON, CSV).

* Nur **Python-Standardbibliothek** (≥ 3.10) – es ist nichts zu installieren.
* **73 Tests**, darunter ein Ende-zu-Ende-Test gegen eine unabhängig festgelegte Ground Truth.
* ~**25.000 Transaktionen/s** (siehe [Skalierbarkeit](#skalierbarkeit)).

## Schnellstart

```bash
git clone https://github.com/alexpavlenkode/transaction-reconciliation.git
cd transaction-reconciliation

python -m txreconcile            # Demo mit data/ -> reports/ (md, html, json, csv)
python -m unittest discover -s tests -t .     # Tests
```

Eigene Dateien:

```bash
python -m txreconcile --db buchungen.db --provider-a abrechnung_a.csv --provider-b abrechnung_b.json --out reports
```

| Option | Bedeutung | Standard |
|---|---|---|
| `--formats md,html,json,csv` | gewünschte Ausgaben | alle |
| `--no-fuzzy` | unscharfe Zuordnung aus | an |
| `--amount-tolerance 0.01` | erlaubte Betragsdifferenz | `0` |
| `--fuzzy-window-days 3` | Zeitfenster der unscharfen Zuordnung | `3` |
| `--high-threshold` / `--medium-threshold` | Prioritätsgrenzen in EUR-Äquivalent | `500` / `50` |
| `--max-matched-rows 100` | Länge der Trefferliste im Markdown-Bericht | `100` |
| `--fail-on-discrepancy` | Exit-Code 1 bei Abweichungen (für CI/Cron) | aus |

Exit-Codes: `0` Lauf ok · `1` Abweichungen gefunden (nur mit `--fail-on-discrepancy`) · `2` Quelle unlesbar / ungültige Eingabe.

Als Bibliothek:

```python
from txreconcile import reconcile_files, ReconcileConfig
result = reconcile_files("data/internal.db", "data/provider_a.csv", "data/provider_b.json")
for item in result.discrepancies:           # bereits nach Priorität und Auswirkung sortiert
    print(item.priority.value, [k.value for k in item.kinds], item.impact)
```

## Ergebnis auf den Testdaten

Beispielbericht: [`examples/report.md`](examples/report.md) · Dashboard: [`examples/report.html`](examples/report.html)
(Datei herunterladen und im Browser öffnen) · [`report.json`](examples/report.json) ·
[`discrepancies.csv`](examples/discrepancies.csv) · [`matched.csv`](examples/matched.csv)

```
Datensätze: 47 DB, 44 Abrechnung  |  zugeordnet: 40 (37 exakt, 3 unscharf)
Nur DB: 6  Nur Abrechnung: 3  Duplikate: 2
Abweichungen: 26 (Hoch 7, Mittel 10, Niedrig 9)  |  Nettoauswirkung: -17.358,91 EUR / +200,00 USD
Importprobleme: 2 Zeilen übersprungen, 1 Warnungen
```

Der Bericht enthält: **Kennzahlen** (je Anbieter, je Befundart, je Priorität, Nettoauswirkung je Währung) →
**priorisierte Abweichungsliste** mit Beschreibung und empfohlener Maßnahme → **nicht zugeordnete** und
**zugeordnete** Transaktionen → **Importprobleme** → **Methodik**.

## Eingabeformate

Drei Quellen, drei Formate – alle werden auf ein gemeinsames Modell (`Transaction`) normalisiert:

| Quelle | Format | Normalisierung |
|---|---|---|
| Interne DB | SQLite (`transactions`: `id, provider, provider_ref, amount, currency, status, created_at[, order_no]`) | read-only geöffnet; `REAL` → `Decimal` über die kürzeste Textdarstellung; Zeiten gelten als UTC |
| Anbieter A | CSV, `;`, deutsche Zahlen `1.234,56`, Datum `TT.MM.JJJJ HH:MM:SS` (UTC), Status auf Deutsch | strikter Parser, BOM-tolerant |
| Anbieter B | JSON, Beträge in **Minor Units** (`{"minor": 12345, "currency": "EUR"}`), ISO-8601 mit Offset | Exponent je Währung (JPY = 0, KWD = 3), Offset → UTC |

Details und die eingebauten Testkonstellationen: [`data/README.md`](data/README.md). Die Testdaten erzeugt
[`scripts/generate_testdata.py`](scripts/generate_testdata.py) deterministisch inklusive `expected.json` (Ground Truth).

## Abgleichslogik

```
Import ──► Normalisierung ──► Matching ──► Abweichungen + Auswirkung ──► Priorität ──► Bericht
 (3 Importer)   (Transaction)   exakt → unscharf    (eine Formel)           (Schwellen)
```

### 1. Zuordnung

1. **Exakt:** gleicher Anbieter + gleiche **normalisierte Referenz** (Großbuchstaben, ohne Leerzeichen/Sonderzeichen:
   `" atx-123 "` = `ATX123`). Hash-Gruppen → O(n).
   *Mehrfache* Einträge mit derselben Referenz werden nach Ähnlichkeit (Währung, Betrag, Zeit) gepaart; der Überschuss
   ist ein **Duplikat** (`DUPLICATE_IN_DB` / `DUPLICATE_IN_PROVIDER`).
2. **Unscharf** (nur für Reste, abschaltbar): gleicher Anbieter + Währung, Zeitfenster ±3 Tage und
   Referenz-Ähnlichkeit (`difflib`). Score = 0,6 · Referenz + 0,3 · Betrag + 0,1 · Zeitnähe, Mindestscore 0,8.
   Weicht auch der Betrag ab, muss die Referenz zu ≥ 92 % übereinstimmen („zwei schwache Indizien ≠ Beweis“).
   Strikt 1:1, bester Score zuerst. Jeder unscharfe Treffer erscheint im Bericht als **zu bestätigen**
   (`REFERENCE_MISMATCH`) – nichts wird stillschweigend „geradegezogen“.

### 2. Abweichungen

| Befund | Bedeutung |
|---|---|
| `MISSING_IN_PROVIDER` | in der DB, aber nicht in der Abrechnung |
| `MISSING_IN_DB` | in der Abrechnung, aber nicht in der DB |
| `AMOUNT_MISMATCH` | gleiche Währung, Betrag weicht ab (mehr als `--amount-tolerance`) |
| `STATUS_MISMATCH` | Status weicht ab (Anbieterwerte werden auf `COMPLETED/PENDING/FAILED/REFUNDED/UNKNOWN` abgebildet) |
| `CURRENCY_MISMATCH` | Währung weicht ab – Beträge werden dann **nicht** verglichen |
| `DUPLICATE_IN_DB` / `DUPLICATE_IN_PROVIDER` | überzähliger Eintrag mit bereits zugeordneter Referenz |
| `REFERENCE_MISMATCH` | nur unscharf zugeordnet |

Ein Datensatz kann mehrere Befunde haben (z. B. Betrag **und** Status).

### 3. Finanzielle Auswirkung

Für jede Seite zählt nur der **verbuchte Betrag**: Betrag, wenn der Status `COMPLETED` ist, sonst 0.

```
Auswirkung = verbuchter Betrag (Anbieter) − verbuchter Betrag (Datenbank)      je Währung
```

* **negativ** = die DB erwartet mehr Geld, als abgerechnet wird (Fehlbetrag, Forderung offen)
* **positiv** = der Anbieter rechnet mehr ab, als die DB kennt (nicht gebuchter Geldeingang)

Dieselbe Formel gilt für *alle* Befundarten. Dadurch wird die Auswirkung bei Datensätzen mit mehreren Befunden
genau **einmal** gezählt, und „ausstehend ↔ fehlgeschlagen“ hat korrekt ±0. Währungen werden nie verrechnet.

### 4. Priorität

| Priorität | Regel |
|---|---|
| 🔴 Hoch | Betrag der Auswirkung ≥ 500 EUR-Äquivalent **oder** Währungsabweichung |
| 🟠 Mittel | ≥ 50 EUR-Äquivalent |
| 🟡 Niedrig | darunter, inkl. ±0 (z. B. „ausstehend, fehlt noch in der Abrechnung“) |

Die Umrechnung (`config.py`, statische Beispielkurse) dient **nur** der Priorisierung, damit 15.800 JPY nicht wie
15.800 EUR behandelt werden. Jede Abweichung bekommt eine Beschreibung und eine **empfohlene Maßnahme**.

## Architektur und Entscheidungen

```
txreconcile/
├── models.py          Transaction, Match, Discrepancy, Status/Priority/IssueKind
├── normalize.py       Referenzen, Beträge (Decimal, Minor Units), Währungen, Zeitstempel
├── importers/         ein Importer je Format (gemeinsame Basisklasse `Importer`)
├── matching.py        exakt + unscharf (Blocking, Zeitfenster, 1:1-Zuordnung)
├── discrepancies.py   Befunde, Auswirkung, Priorität, Texte
├── summary.py         Kennzahlen
├── reconcile.py       Orchestrierung: reconcile() / reconcile_files()
├── report/            markdown.py · html.py · exports.py (json/csv)
└── cli.py             Kommandozeile
```

| Entscheidung | Begründung |
|---|---|
| **Nur Standardbibliothek** | Setup-frei, überall lauffähig; für die Aufgabe sind SQLite, `csv`, `json`, `decimal`, `difflib` ausreichend. |
| **Ein kanonisches Modell** (`Transaction`, unveränderlich) | Matching und Berichte kennen keine Quellformate – eine vierte Quelle bedeutet nur einen neuen `Importer`. |
| **`Decimal` statt `float`, Minor Units pro Währung** | Geld darf nicht „fast“ stimmen; `REAL` aus SQLite wird über seine kürzeste Textform gelesen (19,99 statt 19,9899…). |
| **Zeilenfehler ≠ Abbruch** | Eine kaputte Zeile wird übersprungen **und im Bericht gelistet**; nur eine unlesbare Quelle (fehlt, falsches Format, Spalten fehlen) bricht mit Exit-Code 2 ab. Gibt es zur unlesbaren Zeile eine DB-Buchung, nennt der Befund das ausdrücklich. |
| **Eine Auswirkungsformel** | Konsistent, nachvollziehbar, keine Doppelzählung (siehe oben). |
| **Konservatives Fuzzy-Matching, immer sichtbar** | Ein falscher Treffer verdeckt zwei echte Fehler; ein verpasster Treffer erzeugt „nur“ zwei Meldungen, die ohnehin geprüft werden. Beim Test mit 100.000 Datensätzen lieferte eine erste, lockerere Regel vereinzelt Fehltreffer – daher die strengere Regel bei abweichendem Betrag. |
| **DB nur lesend** (`mode=ro`) | Der Abgleich kann Produktivdaten nicht verändern. |
| **Ground-Truth-Tests** | Der Generator legt die erwarteten Ergebnisse unabhängig vom Produktivcode fest; derselbe Mechanismus prüft auch 1.500 Zufallsdatensätze. |

## Fehlerbehandlung

| Situation | Verhalten |
|---|---|
| Datei fehlt / keine gültige DB / ungültiges JSON / Spalten fehlen | `SourceError` → Meldung, Exit-Code 2 |
| Zeile mit ungültigem Betrag, Zeitstempel, Währung oder ohne ID | Zeile übersprungen, Importproblem *Fehler* im Bericht |
| Unbekannter Status (z. B. `chargeback_initiated`) | übernommen als `UNKNOWN` + *Warnung*; zählt als nicht verbucht und wird als Statusabweichung gemeldet |
| Buchung ohne Provider-Referenz | kann nicht exakt zugeordnet werden → „fehlt in Abrechnung“ mit Hinweis |
| Ungültige CLI-Parameter | Fehlermeldung, Exit-Code 2 |

## Skalierbarkeit

Gemessen mit `python scripts/benchmark.py 10000 100000 300000` (Python 3.11, Windows-Laptop, ~6 % Anomalien;
jeder Lauf prüft zusätzlich, dass **alle** eingebauten Anomalien exakt gefunden werden):

| Transaktionen | Import | Matching | Abweichungen | Pipeline gesamt | Spitzen-Speicher |
|---:|---:|---:|---:|---:|---:|
| 10.000 | 0,3 s | 0,05 s | 0,02 s | 0,4 s | 17 MB |
| 100.000 | 2,5 s | 1,4 s | 0,2 s | 4,1 s | 177 MB |
| 300.000 | 7,8 s | 9,2 s | 0,5 s | 17,5 s | 523 MB |

**Was heute schon skaliert:** exaktes Matching ist O(n) (Hash-Gruppen); die DB wird per Cursor gestreamt; das
Fuzzy-Matching sieht nur die *Reste* und vergleicht nur Kandidaten desselben Anbieters/derselben Währung im
Zeitfenster (sortierte Liste + Bisektion statt Kreuzprodukt), mit billigen Vorfiltern vor der teuren
Ähnlichkeitsberechnung. Das HTML-Dashboard zeigt höchstens 1.000 Treffer, der Markdown-Bericht
`--max-matched-rows`; `report.json`/`matched.csv` enthalten immer alles.

**Grenzen:** alles liegt im Arbeitsspeicher (~1,7 KB je Transaktion); das Fuzzy-Matching wächst mit der Größe des
Rest-Pools überproportional (300.000 → 9 s); `json.load` liest Datei B komplett.

**Nächste Schritte für Millionen Datensätze / Dauerbetrieb:**

1. **Partitionieren:** Abgleich je Anbieter und Zeitraum (Tag/Woche + Nachlaufzeit für späte Abrechnungen); Partitionen sind
   unabhängig und parallel ausführbar (`multiprocessing`/Worker). Nicht abgeschlossene Reste wandern in die nächste Periode.
2. **In die Datenbank verlagern:** Anbieterdateien in eine Staging-Tabelle laden und den exakten Abgleich als
   `FULL OUTER JOIN` über einen Index `(provider, normalisierte_referenz)` ausführen (Hash-/Merge-Join); Python
   bleibt für Normalisierung, Fuzzy-Reste und Berichte.
3. **Streaming-Import:** JSON Lines oder ein Streaming-Parser (`ijson`) für B; Chunking nach Primärschlüssel für die DB.
4. **Fuzzy-Kandidaten per Index:** Trigramm-Index (z. B. `pg_trgm`) oder MinHash/LSH statt Fenster-Scan; zusätzlich
   Betrags-Bucketing, falls die Reste groß sind.
5. **Betrieb:** Ergebnisse (Matches, Befunde, Status „offen/geklärt“) persistieren, damit Läufe **idempotent und
   inkrementell** sind (Watermark je Quelle); Kennzahlen/Alarme (Quote, Nettoauswirkung) ans Monitoring.
6. **Fachlich:** Tageskurse statt statischer Umrechnung, Gebühren/Netto-Beträge je Anbieter, konfigurierbare Regeln je Anbieter.

## Annahmen und bekannte Grenzen

* Die interne Referenz `provider_ref` ist die Transaktions-ID des Anbieters (Join-Schlüssel); Anbieter-IDs sind je Anbieter eindeutig.
* Verglichen werden **Brutto-Beträge**; Gebühren und Auszahlungen (Payouts) sind nicht Teil des Abgleichs.
* Zeitstempel dienen nur der Paarung bei Duplikaten und dem Fuzzy-Matching, nicht als Abweichungskriterium
  (Buchungs- und Abrechnungszeit unterscheiden sich fachlich).
* Interne Buchungen, die jünger sind als der Abrechnungszeitraum des Anbieters, würden als „fehlt in Abrechnung“ gemeldet –
  im Betrieb gehört dafür ein Abrechnungszeitraum-Filter davor (siehe Partitionierung).
* Prioritätsgrenzen und Umrechnungskurse sind Beispielwerte (`config.py` / CLI-Optionen).

## Tests

```bash
python -m unittest discover -s tests -t .
```

| Datei | Inhalt |
|---|---|
| `test_normalize.py` | Referenzen, deutsche Beträge, Minor Units (JPY/KWD), Float-Rauschen, Zeitzonen |
| `test_importers.py` | die drei Formate, Zeilenfehler vs. fatale Fehler (fehlende Datei, falsche Spalten, kaputtes Encoding, ungültiges JSON) |
| `test_matching.py` | exakt, Duplikate, Anbietertrennung, unscharf (Schwellen, Zeitfenster, Währung, 1:1, Köder) |
| `test_discrepancies.py` | Auswirkungsformel, keine Doppelzählung, Toleranz, Prioritätsgrenzen, Sortierung |
| `test_golden.py` | **Ende-zu-Ende gegen `expected.json`**, Bilanz „jeder Datensatz genau einmal“, Summen-Konsistenz, 1.500 Zufallsdatensätze, Generator-Drift |
| `test_reports.py` | Markdown/HTML/JSON/CSV, Script-Injection im HTML, CLI inkl. Exit-Codes |

CI (GitHub Actions) führt die Tests unter Linux und Windows mit Python 3.10, 3.12 und 3.13 aus.

## Entstehung

Entwickelt im Pair-Programming mit **Claude Code**: Aufgabenanalyse, Architektur, Implementierung und Tests entstanden
im Dialog; die fachlichen Entscheidungen (Auswirkungsformel, Fuzzy-Regeln, Prioritäten) sind oben begründet und
durch Tests abgesichert. Das Benchmark deckte dabei einen echten Fehler auf (Fehltreffer beim unscharfen Matching im
Großen), der behoben und per Test fixiert wurde.
