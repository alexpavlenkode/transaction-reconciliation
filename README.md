# Transaktionsabgleich

[![CI](https://github.com/alexpavlenkode/transaction-reconciliation/actions/workflows/ci.yml/badge.svg)](https://github.com/alexpavlenkode/transaction-reconciliation/actions/workflows/ci.yml)

Gleicht die **interne Buchungsdatenbank** mit den Abrechnungen von **Zahlungsdienstleister A** (CSV) und
**Zahlungsdienstleister B** (JSON) ab, erkennt fehlende Einträge sowie Betrags-, Status- und Währungsabweichungen,
berechnet die **finanziellen Auswirkungen** – und sagt ehrlich, wo sich eine Auswirkung *nicht* berechnen lässt –
und erzeugt einen **priorisierten, handlungsorientierten Bericht** (Markdown, HTML-Dashboard, JSON, CSV).

* Nur **Python-Standardbibliothek** (≥ 3.10) – es ist nichts zu installieren.
* **113 Tests**, darunter ein Ende-zu-Ende-Test gegen eine unabhängig festgelegte Ground Truth.
* Reproduzierbar: Stichtag `--as-of` ist Pflicht, der Bericht enthält keine Systemzeit – gleiche Eingabe, gleiche Bytes.

## Schnellstart

```bash
git clone https://github.com/alexpavlenkode/transaction-reconciliation.git
cd transaction-reconciliation

python -m txreconcile --as-of 2025-04-01       # Demo mit data/ -> reports/ (md, html, json, csv)
python -m unittest discover -s tests -t .      # Tests
```

Eigene Dateien:

```bash
python -m txreconcile --as-of 2025-04-01 --db buchungen.db --provider-a abrechnung_a.csv --provider-b abrechnung_b.json --out reports
```

| Option | Bedeutung | Standard |
|---|---|---|
| `--as-of` | **Pflicht.** Stichtag der Auswertung (`2025-04-01` oder `2025-04-01T12:00:00+02:00`); die Eingabedateien müssen den Stand zu diesem Zeitpunkt zeigen | – |
| `--settlement-lag-days` | zulässige Verzögerung bis zur Abrechnung | `3` |
| `--formats md,html,json,csv` | gewünschte Ausgaben | alle |
| `--no-fuzzy` | unscharfe Zuordnung aus | an |
| `--amount-tolerance 0.01` | erlaubte Betragsdifferenz | `0` |
| `--high-threshold` / `--medium-threshold` | Schwere-Schwellen je Währung ohne eigene Schwelle | `500` / `50` |
| `--currency-threshold JPY=75000:7500` | eigene Schwellen einer Währung (wiederholbar) | JPY vorbelegt |
| `--allow-real-amount` | Altbestand: Beträge aus einer `REAL`-Spalte lesen (ungenau, siehe unten) | aus |
| `--csv-timezone Europe/Berlin` | Zone für CSV-Zeiten ohne Offset (Spalte `Zeitstempel`) | `UTC` |
| `--fail-on-discrepancy` | Exit-Code 1 bei Abweichungen (für CI/Cron) | aus |
| `--fail-on-incomplete` | Exit-Code 3, wenn Zeilen übersprungen wurden | aus |

Exit-Codes: `0` ok · `1` Abweichungen (nur mit `--fail-on-discrepancy`) · `2` Quelle unlesbar / ungültige Eingabe ·
`3` Ergebnis unvollständig (nur mit `--fail-on-incomplete`, hat Vorrang vor `1`).

Als Bibliothek:

```python
from datetime import datetime, timezone
from txreconcile import reconcile_files, ReconcileConfig

config = ReconcileConfig(as_of=datetime(2025, 4, 1, tzinfo=timezone.utc))
result = reconcile_files("data/internal.db", "data/provider_a.csv", "data/provider_b.json", config)
for item in result.discrepancies:        # bereits nach Schwere und Größe sortiert
    print(item.priority.value, item.certainty.value, [k.value for k in item.kinds], item.impact, item.affected)
```

## Ergebnis auf den Testdaten

Beispielbericht: [`examples/report.md`](examples/report.md) · Dashboard: [`examples/report.html`](examples/report.html)
(Datei herunterladen und im Browser öffnen) · [`report.json`](examples/report.json) ·
[`discrepancies.csv`](examples/discrepancies.csv) · [`matched.csv`](examples/matched.csv)

```
ACHTUNG: Ergebnis unvollständig – provider_a: 1 Zeile(n) übersprungen; provider_b: 1 Zeile(n) übersprungen, davon 1 ohne lesbare Referenz
Datensätze: 49 DB, 46 Abrechnung  |  zugeordnet: 41 (38 exakt, 3 unscharf)
Nur DB: 7  Nur Abrechnung: 3  Duplikate: 3
Abweichungen: 28 (Hoch 7, Mittel 13, Niedrig 8)  |  berechnete Nettoauswirkung: -16.583,91 EUR
Davon 7 ohne bestimmbare Auswirkung (betroffen: 1.565,00 EUR / 200,00 USD), 1 vorläufig
Importprobleme: 2 Zeilen übersprungen, 1 Warnungen
```

Der Bericht enthält: **Kennzahlen** (je Anbieter, je Befundart, je Schwere; berechnete Auswirkung *getrennt* von nicht
bestimmbaren Fällen) → **priorisierte Abweichungsliste** mit Beschreibung, Sicherheit und empfohlener Maßnahme →
**nicht zugeordnete** und **zugeordnete** Transaktionen → **Importprobleme** → **Methodik**. Bei unvollständigem
Ergebnis steht oben ein Warnhinweis. Die Summen beschreiben Abweichungen *zwischen den Daten*, keinen nachgewiesenen Verlust.

## Datenvertrag (Eingabeformate)

Drei Quellen, drei Formate – alle werden auf ein gemeinsames Modell (`Transaction`) normalisiert. Der Bericht kann nur
so genau sein wie dieser Vertrag, deshalb wird nichts geraten:

| Quelle | Format | Regeln |
|---|---|---|
| Interne DB | SQLite, Tabelle `transactions`: `id, provider, provider_ref, amount_minor, currency, status, created_at[, order_no]` | Read-only geöffnet. **`amount_minor` ist ein INTEGER in Minor Units** (Cent; JPY: Yen). Andere Typen in dieser Spalte → Zeilenfehler. Zeiten ohne Offset gelten als UTC. |
| Anbieter A | CSV, `;`, deutsche Zahlen `1.234,56`, Datum `TT.MM.JJJJ HH:MM:SS`, Status auf Deutsch | Spalte `Zeitstempel (UTC)` = UTC; alternativ `Zeitstempel` = Ortszeit in `--csv-timezone`. Strikter Zahlenparser, BOM-tolerant. |
| Anbieter B | JSON, `amount: {"minor": 12345, "currency": "EUR"}`, ISO-8601 mit Offset | `minor` muss eine JSON-**Ganzzahl** sein (kein `1234.0`, kein Text). |

**`REAL`-Beträge (Altbestand):** Eine Spalte `amount REAL` ist eine Näherung und kann den ursprünglichen Dezimalbetrag nicht
beweisen. Deshalb wird sie standardmäßig **abgelehnt** (Exit-Code 2). Mit `--allow-real-amount` wird sie gelesen – über die
kürzeste Textdarstellung (19,99 statt 19,9899…) und kaufmännisch auf die Währungsgenauigkeit gerundet; das ist korrekt,
solange der Originalbetrag höchstens 15 signifikante Stellen hatte – und der Bericht warnt ausdrücklich.

**Zeit:** Alles wird nach UTC normiert. Ortszeiten ohne Offset brauchen eine definierte Zone; Uhrzeiten, die durch die
Zeitumstellung **mehrdeutig sind oder nicht existieren** (z. B. 26.10.2025 02:30 in Berlin), werden als Zeilenfehler gemeldet
statt geraten. Für IANA-Zonen braucht Windows das Paket `tzdata` (`pip install tzdata`); mit UTC ist nichts nötig.

Details und die eingebauten Testkonstellationen: [`data/README.md`](data/README.md). Die Testdaten erzeugt
[`scripts/generate_testdata.py`](scripts/generate_testdata.py) deterministisch inklusive `expected.json` (Ground Truth).

## Abgleichslogik

```
Import ──► Normalisierung ──► Matching ──► Befunde ──► Auswirkung + Sicherheit ──► Schwere ──► Bericht
 (3 Importer)  (Transaction)  exakt → unscharf          (eine Formel)               (je Währung)
```

**Modell:** Die Quellen sind *Schnappschüsse des Zustands einer Transaktion*, kein Journal einzelner Geldereignisse.
Verglichen werden **Brutto-Beträge** (Gebühren und Auszahlungen sind nicht Teil des Abgleichs).

### 1. Zuordnung

1. **Exakt:** gleicher Anbieter + gleicher **Abgleichsschlüssel**. Der Schlüssel entsteht nach der **ID-Regel des
   Anbieters** (`normalize.ID_RULES`), der Rohwert bleibt erhalten: bei **A** ohne Groß-/Kleinschreibung und ohne
   Trennzeichen (`" atx-123 "` = `ATX123`), bei **B** exakt (nur umgebende Leerzeichen entfallen; `bpay_x` ≠ `BPAY_X`).
   Hash-Gruppen → O(n). *Mehrfache* Einträge mit demselben Schlüssel werden nach Ähnlichkeit gepaart (Währung, Betrag,
   Zeit; bei Gleichstand entscheiden IDs, nie die Eingabereihenfolge); der Überschuss wird als *mehrfacher Eintrag*
   gemeldet. Unterscheiden sich dessen Rohwerte (`ATX-1` vs. `atx1`), kommt **`ID_COLLISION`** hinzu: es könnte eine
   Normalisierungs-Kollision statt eines Duplikats sein.
2. **Unscharf** (nur für Reste, abschaltbar): gleicher Anbieter + Währung, Zeitfenster ±3 Tage und Referenz-Ähnlichkeit
   (`difflib`). Score = 0,6 · Referenz + 0,3 · Betrag + 0,1 · Zeitnähe, Mindestscore 0,8. Weicht auch der Betrag ab,
   muss die Referenz zu ≥ 92 % übereinstimmen („zwei schwache Indizien ≠ Beweis“). Strikt 1:1, bester Score zuerst.
   Jeder unscharfe Treffer erscheint im Bericht als **zu bestätigen** (`REFERENCE_MISMATCH`).

### 2. Befunde

| Befund | Bedeutung |
|---|---|
| `MISSING_IN_PROVIDER` | in der DB, nicht in der Abrechnung – **und die Frist ist abgelaufen** |
| `NOT_YET_DUE` | in der DB, nicht in der Abrechnung, aber noch **innerhalb der Frist** (nur beobachten) |
| `MISSING_IN_DB` | in der Abrechnung, nicht in der DB |
| `SOURCE_ROW_UNREADABLE` | die Gegenseite hat zu dieser Referenz eine **unlesbare Zeile** – „nicht prüfbar“ statt „fehlt“ |
| `AMOUNT_MISMATCH` | gleiche Währung, Betrag weicht ab (mehr als `--amount-tolerance`) |
| `STATUS_MISMATCH` | Status weicht ab (Anbieterwerte → `COMPLETED/PENDING/FAILED/REFUNDED/UNKNOWN`) |
| `CURRENCY_MISMATCH` | Währung weicht ab – Beträge werden **nicht** verglichen |
| `DUPLICATE_IN_DB` / `DUPLICATE_IN_PROVIDER` | überzähliger Eintrag mit bereits zugeordneter Referenz |
| `ID_COLLISION` | der überzählige Eintrag unterscheidet sich vor der Normalisierung |
| `REFERENCE_MISMATCH` | nur unscharf zugeordnet |

Ein Datensatz kann mehrere Befunde haben (z. B. Betrag **und** Status).

### 3. Finanzielle Auswirkung – und wann es keine gibt

Pro Seite zählt der **verbuchte Betrag**:

| Status | verbuchter Betrag |
|---|---|
| `COMPLETED` | der Betrag |
| `PENDING`, `FAILED` | 0 |
| `REFUNDED` | 0 (vollständige Erstattung im Schnappschuss-Modell) |
| `UNKNOWN` | **nicht bestimmt** – ausdrücklich *nicht* 0 |

```
Auswirkung = verbuchter Betrag (Anbieter) − verbuchter Betrag (Datenbank)      je Währung, ohne Umrechnung
```

* **negativ** = die DB erwartet mehr Geld, als abgerechnet wird · **positiv** = der Anbieter rechnet mehr ab, als die DB kennt
* eine Formel für alle Befunde mit bestimmbarer Auswirkung; bei mehreren Befunden an einem Datensatz wird sie **einmal** gezählt
* eine Auswirkung von 0 hebt den Befund nicht auf (z. B. „ausstehend ↔ fehlgeschlagen“ bleibt in der Liste)

**Nicht bestimmbar (`UNDEFINED`)** ist die Auswirkung bei: unbekanntem Status (ein erfundener Nullwert wäre eine erfundene
Abweichung), Währungsabweichung (kein Kurs, keine Subtraktion), mehrfachen Einträgen und ID-Kollisionen (doppelte *Zeile*
oder doppelte *Zahlung*? aus den Daten nicht entscheidbar), unlesbarer Gegenzeile und Buchungen innerhalb der Frist.
Dort steht **nur der betroffene Betrag** (`affected`: der größere Betrag der beteiligten Datensätze je Währung); er wird
nie in die Auswirkungssumme gemischt, sondern in der Zusammenfassung getrennt ausgewiesen.

**Vorläufig (`PRELIMINARY`):** Enthält eine Quelle Zeilen **ohne lesbare Referenz**, könnte jede „fehlt“-Aussage zu dieser Seite
dadurch erklärt werden. Die Auswirkung wird berechnet und gezählt, ist aber als vorläufig markiert.

### 4. Schwere und Sicherheit – zwei getrennte Felder

* **Schwere** (hoch / mittel / niedrig) nach **Schwellen je Währung** (`500 / 50`, JPY `75.000 / 7.500`; ohne Kurse).
  Maßgeblich ist die berechnete Auswirkung, bei nicht bestimmbarer Auswirkung der betroffene Betrag – ein großer,
  unklarer Duplikat-Fall ist also **hoch**, obwohl keine Auswirkung berechnet wird. Währungskonflikte sind immer hoch;
  ein überfälliger „fehlt“-Befund ist mindestens mittel; „noch nicht fällig“ ist niedrig.
* **Sicherheit** (berechnet / vorläufig / nicht bestimmbar): wie belastbar die Zahl ist.

### 5. Stichtag und Frist

`--as-of` legt den Auswertungszeitpunkt fest; die Systemuhr geht nie in das Ergebnis ein. Eine Buchung ist **überfällig
genau dann, wenn `as_of > Buchungszeit + Frist`** (strikt größer; genau am Fristende ist sie noch nicht fällig). Die
Eingabedateien müssen den Stand zu diesem Zeitpunkt zeigen; Datensätze *nach* dem Stichtag erzeugen eine Warnung, weil
die Datei dann nicht zum Stichtag passt. Ein früherer Stichtag auf einem später gezogenen Export lässt sich nicht
rekonstruieren – dafür bräuchte man Historie in den Quellen.

## Fehlerbehandlung und unvollständige Ergebnisse

| Situation | Verhalten |
|---|---|
| Datei fehlt / keine gültige DB / ungültiges JSON / Spalten fehlen / `REAL` ohne Altbestands-Modus | `SourceError` → Meldung, **Exit-Code 2**, kein Abgleich (eine unvollständig gelesene Quelle würde falsche Befunde erzeugen) |
| Zeile mit ungültigem Betrag, Zeitstempel, Währung oder ohne ID | Zeile übersprungen, Importproblem *Fehler*; Ergebnis wird **als unvollständig markiert** (Warnbanner, `incomplete` im JSON, Exit-Code 3 mit `--fail-on-incomplete`) |
| … die ID der Zeile war lesbar | die Gegenseite dieser Referenz wird **„nicht prüfbar“** (kein falsches „fehlt“, keine Auswirkung gezählt) |
| … die ID war nicht lesbar | alle „fehlt“-Befunde der betroffenen Quelle sind **vorläufig** |
| Unbekannter Status (z. B. `chargeback_initiated`) | als `UNKNOWN` übernommen + *Warnung*; Auswirkung nicht bestimmbar, nur der betroffene Betrag |
| Buchung ohne Provider-Referenz | kann nicht exakt zugeordnet werden → „fehlt in Abrechnung“ mit Hinweis |

## Architektur und Entscheidungen

```
txreconcile/
├── models.py          Transaction, Match, Discrepancy, Status/Priority/Certainty/IssueKind
├── normalize.py       ID-Regeln je Anbieter, Beträge (Minor Units, Decimal), Währungen, Zeit/Zeitzonen
├── importers/         ein Importer je Format (gemeinsame Basisklasse `Importer`)
├── matching.py        exakt + unscharf (Blocking, Zeitfenster, 1:1, deterministische Tie-Breaks)
├── discrepancies.py   Befunde, Auswirkung, Sicherheit, Fälligkeit, Schwere, Texte
├── summary.py         Kennzahlen (berechnet vs. nicht bestimmbar getrennt)
├── reconcile.py       Orchestrierung: reconcile() / reconcile_files(), Unvollständigkeit
├── report/            markdown.py · html.py · exports.py (json/csv)
└── cli.py             Kommandozeile
```

| Entscheidung | Begründung |
|---|---|
| **Nur Standardbibliothek** | Setup-frei, überall lauffähig; SQLite, `csv`, `json`, `decimal`, `difflib` genügen. |
| **Ein kanonisches Modell** (`Transaction`, unveränderlich) | Matching und Berichte kennen keine Quellformate – eine vierte Quelle bedeutet nur einen neuen `Importer`. |
| **`Decimal`, Minor Units strikt, `REAL` nur als benannter Altbestands-Modus** | Geld darf nicht „fast“ stimmen; eine Näherung wird nicht stillschweigend zur Wahrheit erklärt. |
| **ID-Regel gehört zum Anbieter** | Ob `abc` = `ABC` gilt, bestimmt das Anbieterformat, nicht das Programm; Kollisionen werden gemeldet statt verschluckt. |
| **Eine Auswirkungsformel + ausdrücklich „nicht bestimmbar“** | Konsistent und ohne Doppelzählung; wo die Daten eine Zahl nicht hergeben, wird keine erfunden. |
| **Schwere ≠ Sicherheit** | Wie dringend etwas ist, und wie belastbar die Zahl dazu ist, sind verschiedene Fragen. |
| **Schwellen je Währung statt Kursen** | Kein Kursquellen-/Datums-Problem, nichts Erfundenes; Sortierung über Betrag relativ zur Schwelle. |
| **Zeilenfehler ≠ Abbruch, aber nie still** | Eine kaputte Zeile wird übersprungen, gelistet und macht das Ergebnis *unvollständig*; nur eine unlesbare Quelle bricht ab. |
| **Konservatives Fuzzy-Matching, immer sichtbar** | Ein falscher Treffer verdeckt zwei echte Fehler. Beim Test mit 100.000 Datensätzen lieferte eine lockerere Regel vereinzelt Fehltreffer – daher die strengere Regel bei abweichendem Betrag. |
| **Deterministisch** | Keine Systemuhr, Tie-Breaks über IDs: Permutation der Eingabezeilen ändert das Ergebnis nicht (getestet). |
| **DB nur lesend** (`mode=ro`) | Der Abgleich kann Produktivdaten nicht verändern. |
| **Ground-Truth-Tests** | Der Generator legt die erwarteten Ergebnisse unabhängig vom Produktivcode fest; derselbe Mechanismus prüft auch 1.500 Zufallsdatensätze. |

## Skalierbarkeit

Gemessen mit `python scripts/benchmark.py 10000 100000 300000` (Python 3.11, Windows-Laptop, ~6 % Anomalien; jeder Lauf
prüft zusätzlich, dass **alle** eingebauten Anomalien exakt gefunden werden). Zeiten schwanken je nach Maschine:

| Transaktionen | Import | Matching | Befunde | Pipeline gesamt | Spitzen-Speicher |
|---:|---:|---:|---:|---:|---:|
| 10.000 | 0,3 s | 0,05 s | 0,02 s | 0,4 s | 17 MB |
| 100.000 | 2,7 s | 1,8 s | 0,2 s | 4,7 s | 172 MB |
| 300.000 | 8,9 s | 13,7 s | 0,7 s | 23 s | 506 MB |

**Was heute schon skaliert:** exaktes Matching ist O(n) (Hash-Gruppen); die DB wird per Cursor gestreamt; das Fuzzy-Matching
sieht nur die *Reste* und vergleicht nur Kandidaten desselben Anbieters/derselben Währung im Zeitfenster (sortierte Liste
+ Bisektion statt Kreuzprodukt) mit billigen Vorfiltern. Das HTML-Dashboard zeigt höchstens 1.000 Treffer, der
Markdown-Bericht `--max-matched-rows`; `report.json`/`matched.csv` enthalten immer alles.

**Grenzen:** alles liegt im Arbeitsspeicher (~1,7 KB je Transaktion); das Fuzzy-Matching wächst mit der Größe des
Rest-Pools überproportional; `json.load` liest Datei B komplett.

**Nächste Schritte für Millionen Datensätze / Dauerbetrieb:**

1. **Partitionieren nach Anbieter und Hash des normalisierten Schlüssels** (nicht nach Zeitraum!): so landen beide Seiten
   eines Paares sicher in derselben Partition, auch an Datumsgrenzen. Partitionen sind unabhängig und parallel
   ausführbar. Das Fuzzy-Matching braucht danach einen **zweiten Durchgang über die Reste aller Partitionen** – ein
   Tippfehler in der Referenz ändert den Hash und trennt das Paar sonst. Der Fristfilter (`NOT_YET_DUE`) ist davon unabhängig.
2. **In die Datenbank verlagern:** Anbieterdateien in eine Staging-Tabelle laden und den exakten Abgleich als
   `FULL OUTER JOIN` über einen Index `(provider, normalisierter_schlüssel)` ausführen; Python bleibt für
   Normalisierung, Fuzzy-Reste und Berichte.
3. **Streaming-Import:** JSON Lines oder ein Streaming-Parser (`ijson`) für B; Chunking nach Primärschlüssel für die DB.
   Streaming allein genügt nicht, wenn danach doch alle Datensätze im Speicher gehalten werden – darum 1 und 2.
4. **Fuzzy-Kandidaten per Index:** Trigramm-Index (z. B. `pg_trgm`) oder MinHash/LSH statt Fenster-Scan.
5. **Betrieb:** Ergebnisse (Matches, Befunde, Status „offen/geklärt“) persistieren, damit Läufe **idempotent und inkrementell**
   sind; Kennzahlen/Alarme (Quote, Nettoauswirkung, Anzahl „nicht bestimmbar“) ans Monitoring.
6. **Fachlich:** Teilerstattungen und Ereignisjournale (statt Schnappschüsse), Gebühren/Netto-Beträge, anbieterspezifische Regeln.

## Annahmen und bekannte Grenzen

* Die interne Referenz `provider_ref` ist die Transaktions-ID des Anbieters (Join-Schlüssel); Anbieter-IDs sind je Anbieter eindeutig.
* **Schnappschuss-Modell:** `REFUNDED` bedeutet vollständige Erstattung (verbuchter Betrag 0). Teilerstattungen und
  Ereignisjournale (ein Eintrag je Geldbewegung, Erstattung als negative Buchung) sind **nicht** abgebildet und brauchen eine
  eigene Regel.
* Zeitstempel dienen der Paarung bei Mehrfacheinträgen, dem Fuzzy-Matching und der Fristprüfung, nicht als Abweichungskriterium.
* Die Eingabedateien müssen zum Stichtag passen (gleicher Exportstand, abgestimmter Zeitraum); das Programm warnt nur,
  wenn Datensätze *nach* dem Stichtag liegen.
* Schwellen sind Beispielwerte (`config.py` / CLI-Optionen); ohne Kurse werden Währungen nie verrechnet.

## Tests

```bash
python -m unittest discover -s tests -t .
```

| Datei | Inhalt |
|---|---|
| `test_normalize.py` | ID-Regeln je Anbieter, deutsche Beträge, strikte Minor Units (JPY/KWD), `REAL`-Modus, Zeitzonen inkl. Zeitumstellung |
| `test_importers.py` | die drei Formate, Zeilenfehler vs. fatale Fehler, strikte Beträge, `REAL`-Ablehnung/-Altbestand, CSV-Zeitzone |
| `test_matching.py` | exakt, Duplikate, Anbietertrennung, ID-Regeln, Reihenfolge-Unabhängigkeit, unscharf (Schwellen, Fenster, Währung, 1:1, Köder) |
| `test_discrepancies.py` | Auswirkungsformel, **nicht bestimmbare Fälle**, Fristgrenze (strikt), nicht prüfbare Zeilen, vorläufige Befunde, Schwellen je Währung |
| `test_golden.py` | **Ende-zu-Ende gegen `expected.json`**, Bilanz „jeder Datensatz genau einmal“, Summen-Konsistenz, **Permutationstest**, 1.500 Zufallsdatensätze, Generator-Drift |
| `test_reports.py` | Markdown/HTML/JSON/CSV, Warnbanner, byte-genaue Reproduzierbarkeit, Script-Injection im HTML, CLI inkl. Exit-Codes und Pflicht-`--as-of` |

Die Zeitzonen-Tests laufen nur, wenn `tzdata`/IANA-Daten verfügbar sind (sonst *skipped*). CI (GitHub Actions) führt alles unter
Linux und Windows mit Python 3.10, 3.12 und 3.13 aus und prüft, dass `examples/` exakt dem aktuellen Programmstand entspricht.

## Zuordnung zu den Bewertungskriterien (Plan, durch Tests belegt)

| Kriterium | Wo |
|---|---|
| Datenimport (3 Formate) | SQLite / CSV / JSON, Importer, strikte Parser, `test_importers.py` |
| Abweichungen + finanzielle Auswirkung | `discrepancies.py`, Abschnitt 2–3, `test_discrepancies.py`, `test_golden.py` |
| Bericht | `report/`, [`examples/`](examples/): Kennzahlen, Schwere × Sicherheit, Maßnahmen, (nicht) zugeordnete Transaktionen |
| Codequalität | getrennte Schichten, Fehlerbehandlung in zwei Stufen, Tests |
| Dokumentation | dieses README (Datenvertrag, Logik, Entscheidungen, Skalierbarkeit) |
| Zusatzaufgaben | Fuzzy Matching, Benchmark, HTML-Dashboard, CI |

## Entstehung

Entwickelt im Pair-Programming mit **Claude Code**: Aufgabenanalyse, Architektur, Implementierung und Tests entstanden im
Dialog. Die fachlichen Entscheidungen (Auswirkungsmodell, „nicht bestimmbar“, Fuzzy-Regeln, Schwellen) wurden in mehreren
Review-Runden kritisch hinterfragt und überarbeitet; Benchmark und Permutationstest deckten reale Fehler auf (Fehltreffer beim
unscharfen Matching im Großen), die behoben und per Test fixiert wurden.
