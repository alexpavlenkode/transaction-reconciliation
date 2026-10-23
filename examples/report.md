# Transaktionsabgleich – Bericht

*Stichtag: **01.04.2025 00:00 UTC** · Frist: 3 Tage · Quellen: `internal.db`, `provider_a.csv`, `provider_b.json`*

> ⚠️ **Ergebnis unvollständig.** provider_a: 1 Zeile(n) übersprungen; provider_b: 1 Zeile(n) übersprungen, davon 1 ohne lesbare Referenz. Zeilen mit lesbarer Referenz sind als „nicht prüfbar“ markiert; wo keine Referenz lesbar war, sind alle „fehlt“-Befunde der betroffenen Quelle **vorläufig** (siehe Abschnitt 5).

## 1. Zusammenfassung

**41 Paare zugeordnet** (38 exakt, 3 unscharf), davon 26 ohne Abweichung. **28 Abweichungen**, davon **7 mit hoher Priorität**. Berechnete Nettoauswirkung (Abrechnung − Datenbank): **-16.583,91 EUR**; Bruttovolumen: 18.409,89 EUR.

**7 Befunde ohne bestimmbare Auswirkung** (betroffener Betrag 1.565,00 EUR / 200,00 USD) sind **nicht** in diesen Summen enthalten – sie brauchen eine Klärung (Duplikat, Währung, unbekannter Status, unlesbare Quellzeile, noch nicht fällig).

1 Befunde sind **vorläufig** (in den Summen enthalten, können sich aber ändern).

> Die Summen beschreiben Abweichungen **zwischen den Daten**, keinen nachgewiesenen Verlust.

### Kennzahlen

| Kennzahl | Wert |
|---|---|
| Datensätze interne Datenbank | 49 |
| Datensätze Abrechnungen (A + B) | 46 |
| Zugeordnete Paare | 41 (38 exakt · 3 unscharf) |
| Zuordnungsquote (Datensätze beider Seiten) | 86,3% |
| Davon fehlerfrei (ohne Abweichung) | 26 (54,7%) |
| Nur in Datenbank (fehlt in Abrechnung) | 7 |
| Nur in Abrechnung (fehlt in Datenbank) | 3 |
| Überzählige Einträge (Duplikate) | 3 |
| Abweichungen gesamt | 28 |
| Davon Auswirkung berechnet / vorläufig / nicht bestimmbar | 20 / 1 / 7 |
| Importprobleme (Zeilen übersprungen / Warnungen) | 2 / 1 |

### Nach Anbieter

| Anbieter | DB | Abrechnung | Zugeordnet | Nur DB | Nur Abrechnung | Duplikate | Abweichungen | Berechnete Auswirkung | Nicht bestimmbar |
|---|---|---|---|---|---|---|---|---|---|
| A | 32 | 30 | 26 | 6 | 2 | 2 | 20 | -15.293,91 EUR | 4 (betroffen: 890,00 EUR) |
| B | 17 | 16 | 15 | 1 | 1 | 1 | 8 | -1.290,00 EUR | 3 (betroffen: 675,00 EUR / 200,00 USD) |

### Abweichungen nach Hauptbefund

Jede Abweichung wird genau einmal gezählt (Hauptbefund = schwerster Einzelbefund); ein Datensatz kann zusätzliche Nebenbefunde haben.

| Befund | Anzahl | Berechnete Auswirkung (Abrechnung − DB) | Nicht bestimmbar |
|---|---|---|---|
| Währungsabweichung | 1 | ±0 | 1 (betroffen: 200,00 EUR / 200,00 USD) |
| Nicht prüfbar (Quellzeile unlesbar) | 1 | ±0 | 1 (betroffen: 410,00 EUR) |
| Fehlt in Abrechnung | 5 | -2.116,00 EUR | — |
| Fehlt in Datenbank | 3 | +747,99 EUR | — |
| Noch nicht fällig | 1 | ±0 | 1 (betroffen: 75,00 EUR) |
| Mehrfach in Datenbank | 1 | ±0 | 1 (betroffen: 145,00 EUR) |
| Mehrfach in Abrechnung | 2 | ±0 | 2 (betroffen: 405,00 EUR) |
| Statusabweichung | 7 | -4.424,90 EUR | 1 (betroffen: 330,00 EUR) |
| Betragsabweichung | 5 | -10.791,00 EUR | — |
| Unscharfe Zuordnung | 2 | ±0 | — |

### Nach Priorität (Schwere)

Schwellen je Währung (hoch / mittel): Standard 500,00 / 50,00; JPY 75.000 / 7.500. Maßgeblich ist die berechnete Auswirkung, bei nicht bestimmbarer Auswirkung der betroffene Betrag. Währungskonflikte sind immer hoch; überfällige „fehlt“-Befunde mindestens mittel.

| Priorität | Anzahl | Bedeutung |
|---|---|---|
| 🔴 Hoch | 7 | sofort klären |
| 🟠 Mittel | 13 | zeitnah klären |
| 🟡 Niedrig | 8 | geringe oder keine Wirkung – im Regelprozess prüfen |

## 2. Priorisierte Abweichungen

Sortiert nach Priorität, dann nach Größe (relativ zur Schwelle der Währung). Die Nummern (D-xxx) sind in `discrepancies.csv` und `report.json` identisch. *Sicherheit* sagt, wie belastbar die Auswirkung ist, unabhängig von der Priorität.

### 🔴 Priorität Hoch (7)

| Nr. | Befund | Anbieter | DB-ID | Anbieter-ID | Datenbank | Anbieter | Auswirkung | Sicherheit | Empfohlene Maßnahme |
|---|---|---|---|---|---|---|---|---|---|
| D-001 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 12.000,00 EUR vs. Anbieter 1.200,00 EUR (Differenz -10.800,00 EUR). | A | 1017 | ATX-28268772 | 12.000,00 EUR · abgeschlossen | 1.200,00 EUR · abgeschlossen | -10.800,00 EUR | berechnet | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-002 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter erstattet. | A | 1020 | ATX-87490478 | 2.500,00 EUR · abgeschlossen | 2.500,00 EUR · erstattet | -2.500,00 EUR | berechnet | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-003 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 1.800,00 EUR (abgeschlossen) vom 04.03.2025 20:19; Abrechnung von Anbieter A enthält keinen Eintrag, obwohl die Frist von 3 Tagen abgelaufen ist. | A | 1023 | — | 1.800,00 EUR · abgeschlossen | — | -1.800,00 EUR | berechnet | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-004 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter fehlgeschlagen. | B | 1044 | bpay_82ee6d74f5 | 1.150,00 EUR · abgeschlossen | 1.150,00 EUR · fehlgeschlagen | -1.150,00 EUR | berechnet | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-005 | **Fehlt in Datenbank**<br>Nur in der Abrechnung von Anbieter A: 640,00 EUR (abgeschlossen) vom 04.03.2025 22:19; keine passende Buchung in der Datenbank. | A | — | ATX-85523351 | — | 640,00 EUR · abgeschlossen | +640,00 EUR | berechnet | Geldeingang dem passenden Vorgang zuordnen und nachbuchen. |
| D-006 | **Statusabweichung, Betragsabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter ausstehend. Betrag weicht ab: Datenbank 500,00 EUR vs. Anbieter 450,00 EUR (Differenz -50,00 EUR). | A | 1022 | ATX-81349318 | 500,00 EUR · abgeschlossen | 450,00 EUR · ausstehend | -500,00 EUR | berechnet | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-007 | **Währungsabweichung**<br>Währung weicht ab: Datenbank 200,00 EUR vs. Anbieter 200,00 USD; die Beträge sind nicht vergleichbar, eine Auswirkung wird ohne Kurs nicht berechnet. | B | 1042 | bpay_5dbdcb245d | 200,00 EUR · abgeschlossen | 200,00 USD · abgeschlossen | nicht bestimmbar (betroffen: 200,00 EUR / 200,00 USD) | nicht bestimmbar | Währung der Buchung gegen den Beleg prüfen und Fehlbuchung korrigieren. |

### 🟠 Priorität Mittel (13)

| Nr. | Befund | Anbieter | DB-ID | Anbieter-ID | Datenbank | Anbieter | Auswirkung | Sicherheit | Empfohlene Maßnahme |
|---|---|---|---|---|---|---|---|---|---|
| D-008 | **Nicht prüfbar (Quellzeile unlesbar)**<br>Nicht prüfbar: Nur in der Datenbank: 410,00 EUR (abgeschlossen) vom 27.03.2025 02:53. Zu dieser Referenz enthält die Abrechnung von Anbieter A eine unlesbare Zeile (Zeile 3: Zeile übersprungen: ungültiger Betrag: 'n/a'). Ob ein Eintrag fehlt, lässt sich erst nach Korrektur der Quelle sagen. | A | 1027 | — | 410,00 EUR · abgeschlossen | — | nicht bestimmbar (betroffen: 410,00 EUR) | nicht bestimmbar | Unlesbare Zeile in der Quelle korrigieren oder neu anfordern und den Abgleich wiederholen. |
| D-009 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter fehlgeschlagen. | A | 1018 | ATX-21622603 | 349,90 EUR · abgeschlossen | 349,90 EUR · fehlgeschlagen | -349,90 EUR | berechnet | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-010 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter unbekannt ('chargeback_initiated'). Der Status ist unbekannt: die Auswirkung ist nicht bestimmbar, nur der betroffene Betrag wird ausgewiesen. | B | 1045 | bpay_cc50b8a435 | 330,00 EUR · abgeschlossen | 330,00 EUR · unbekannt | nicht bestimmbar (betroffen: 330,00 EUR) | nicht bestimmbar | Unbekannten Anbieterstatus beim Anbieter erfragen und in die Statuszuordnung aufnehmen. |
| D-011 | **Mehrfach in Abrechnung**<br>Mehrfacher Eintrag in der Abrechnung: Referenz 'ATX-49497139' kommt mehrfach vor (310,00 EUR); ein Eintrag ist bereits der DB-ID 1029 zugeordnet. Ob doppelte Zahlung oder doppelte Zeile, ist aus den Daten nicht bestimmbar – betroffener Betrag, keine berechnete Auswirkung. | A | — | ATX-49497139 | — | 310,00 EUR · abgeschlossen | nicht bestimmbar (betroffen: 310,00 EUR) | nicht bestimmbar | Beim Anbieter klären, ob doppelt belastet wurde; bei Doppelbelastung reklamieren. |
| D-012 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 210,00 EUR (abgeschlossen) vom 26.03.2025 09:43; Abrechnung von Anbieter B enthält keinen Eintrag, obwohl die Frist von 3 Tagen abgelaufen ist. Vorläufig: die Quelle enthält Zeilen ohne lesbare Referenz, die diesen Befund erklären könnten. | B | 1046 | — | 210,00 EUR · abgeschlossen | — | -210,00 EUR (vorläufig) | vorläufig | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-013 | **Mehrfach in Datenbank**<br>Mehrfacher Eintrag in der Datenbank: Referenz 'bpay_f44286b855' kommt mehrfach vor (145,00 EUR); ein Eintrag ist bereits dem Anbietereintrag zugeordnet (DB-ID 1047). Ob Doppelbuchung oder Doppelzeile, ist aus den Daten nicht bestimmbar – betroffener Betrag, keine berechnete Auswirkung. | B | 1048 | — | 145,00 EUR · abgeschlossen | — | nicht bestimmbar (betroffen: 145,00 EUR) | nicht bestimmbar | Prüfen, ob eine Doppelbuchung oder nur eine doppelte Zeile vorliegt; Doppelbuchung stornieren. |
| D-014 | **Mehrfach in Abrechnung, Mögliche ID-Kollision**<br>Mehrfacher Eintrag in der Abrechnung: Referenz 'atx84860779' kommt mehrfach vor (95,00 EUR); ein Eintrag ist bereits der DB-ID 1030 zugeordnet. Ob doppelte Zahlung oder doppelte Zeile, ist aus den Daten nicht bestimmbar – betroffener Betrag, keine berechnete Auswirkung. Mögliche ID-Kollision: 'atx84860779' und 'ATX-84860779' sind nur nach der Normalisierung gleich (Regel des Anbieters A); es kann sich um verschiedene Transaktionen handeln. | A | — | atx84860779 | — | 95,00 EUR · abgeschlossen | nicht bestimmbar (betroffen: 95,00 EUR) | nicht bestimmbar | Beim Anbieter klären, ob doppelt belastet wurde; bei Doppelbelastung reklamieren. Rohwerte der IDs gegen den Beleg prüfen und ggf. die ID-Regel des Anbieters anpassen. |
| D-015 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 899,00 EUR vs. Anbieter 989,00 EUR (Differenz +90,00 EUR). | A | 1016 | ATX-42675569 | 899,00 EUR · abgeschlossen | 989,00 EUR · abgeschlossen | +90,00 EUR | berechnet | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-016 | **Fehlt in Datenbank**<br>Nur in der Abrechnung von Anbieter B: 88,00 EUR (abgeschlossen) vom 26.03.2025 10:54; keine passende Buchung in der Datenbank. | B | — | bpay_5e5b78866a | — | 88,00 EUR · abgeschlossen | +88,00 EUR | berechnet | Geldeingang dem passenden Vorgang zuordnen und nachbuchen. |
| D-017 | **Statusabweichung**<br>Status weicht ab: Datenbank ausstehend vs. Anbieter abgeschlossen. | A | 1019 | ATX-47281038 | 75,00 EUR · ausstehend | 75,00 EUR · abgeschlossen | +75,00 EUR | berechnet | Status in der Datenbank aktualisieren (Zahlung ist beim Anbieter abgeschlossen). |
| D-018 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 64,00 EUR (abgeschlossen) vom 12.03.2025 08:19; Abrechnung von Anbieter A enthält keinen Eintrag, obwohl die Frist von 3 Tagen abgelaufen ist. Es ist keine Provider-Referenz hinterlegt. | A | 1026 | — | 64,00 EUR · abgeschlossen | — | -64,00 EUR | berechnet | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-019 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 42,00 EUR (abgeschlossen) vom 02.03.2025 17:09; Abrechnung von Anbieter A enthält keinen Eintrag, obwohl die Frist von 3 Tagen abgelaufen ist. | A | 1024 | — | 42,00 EUR · abgeschlossen | — | -42,00 EUR | berechnet | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-020 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 120,00 EUR (ausstehend) vom 13.03.2025 05:03; Abrechnung von Anbieter A enthält keinen Eintrag, obwohl die Frist von 3 Tagen abgelaufen ist. | A | 1025 | — | 120,00 EUR · ausstehend | — | ±0 | berechnet | Buchung ist nicht abgeschlossen: beim Anbieter den Stand erfragen, da die Frist abgelaufen ist. |

### 🟡 Priorität Niedrig (8)

| Nr. | Befund | Anbieter | DB-ID | Anbieter-ID | Datenbank | Anbieter | Auswirkung | Sicherheit | Empfohlene Maßnahme |
|---|---|---|---|---|---|---|---|---|---|
| D-021 | **Noch nicht fällig**<br>Noch nicht fällig: Buchung vom 31.03.2025 12:00 (75,00 EUR, abgeschlossen); die Abrechnung wird bis 03.04.2025 12:00 erwartet (Stichtag 01.04.2025 00:00). | A | 1028 | — | 75,00 EUR · abgeschlossen | — | nicht bestimmbar (betroffen: 75,00 EUR) | nicht bestimmbar | Nichts tun: bis zum Fristende abwarten und erneut abgleichen. |
| D-022 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 1.250,00 EUR vs. Anbieter 1.205,00 EUR (Differenz -45,00 EUR). | A | 1015 | ATX-36588931 | 1.250,00 EUR · abgeschlossen | 1.205,00 EUR · abgeschlossen | -45,00 EUR | berechnet | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-023 | **Fehlt in Datenbank**<br>Nur in der Abrechnung von Anbieter A: 19,99 EUR (abgeschlossen) vom 17.03.2025 09:51; keine passende Buchung in der Datenbank. | A | — | ATX-47573247 | — | 19,99 EUR · abgeschlossen | +19,99 EUR | berechnet | Geldeingang dem passenden Vorgang zuordnen und nachbuchen. |
| D-024 | **Betragsabweichung, Unscharfe Zuordnung**<br>Betrag weicht ab: Datenbank 220,00 EUR vs. Anbieter 202,00 EUR (Differenz -18,00 EUR). Zuordnung über unscharfe Suche: Referenz 'ATX-85695696' (DB) ↔ 'TX-85695696' (Anbieter), Konfidenz 95%. | A | 1032 | TX-85695696 | 220,00 EUR · abgeschlossen | 202,00 EUR · abgeschlossen | -18,00 EUR | berechnet | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. Zuordnung bestätigen und die Referenz in der Datenbank korrigieren. |
| D-025 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 75,50 EUR vs. Anbieter 57,50 EUR (Differenz -18,00 EUR). | B | 1043 | bpay_9a3aad9bb6 | 75,50 EUR · abgeschlossen | 57,50 EUR · abgeschlossen | -18,00 EUR | berechnet | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-026 | **Statusabweichung**<br>Status weicht ab: Datenbank ausstehend vs. Anbieter fehlgeschlagen. | A | 1021 | ATX-53501687 | 33,00 EUR · ausstehend | 33,00 EUR · fehlgeschlagen | ±0 | berechnet | Status mit dem Anbieter klären; derzeit keine finanzielle Wirkung. |
| D-027 | **Unscharfe Zuordnung**<br>Zuordnung über unscharfe Suche: Referenz 'bpay_7481d856c7' (DB) ↔ 'bpay_748d856c7' (Anbieter), Konfidenz 98%. | B | 1049 | bpay_748d856c7 | 62,00 EUR · abgeschlossen | 62,00 EUR · abgeschlossen | ±0 | berechnet | Zuordnung bestätigen und die Referenz in der Datenbank korrigieren. |
| D-028 | **Unscharfe Zuordnung**<br>Zuordnung über unscharfe Suche: Referenz 'ATX-47001509' (DB) ↔ 'ATX-4700150O' (Anbieter), Konfidenz 94%. | A | 1031 | ATX-4700150O | 180,00 EUR · abgeschlossen | 180,00 EUR · abgeschlossen | ±0 | berechnet | Zuordnung bestätigen und die Referenz in der Datenbank korrigieren. |

## 3. Nicht zugeordnete Transaktionen

### 3.1 Nur in der Datenbank (8)

| Nr. | Priorität | Anbieter | ID | Referenz | Betrag | Status | Zeitpunkt | Bestellung | Befund | Auswirkung |
|---|---|---|---|---|---|---|---|---|---|---|
| D-003 | 🔴 Hoch | A | 1023 | ATX-85523350 | 1.800,00 EUR | abgeschlossen | 04.03.2025 20:19 | SO-27161 | Fehlt in Abrechnung | -1.800,00 EUR |
| D-008 | 🟠 Mittel | A | 1027 | ATX-83009462 | 410,00 EUR | abgeschlossen | 27.03.2025 02:53 | SO-27189 | Nicht prüfbar (Quellzeile unlesbar) | nicht bestimmbar (betroffen: 410,00 EUR) |
| D-012 | 🟠 Mittel | B | 1046 | bpay_b95a5ea040 | 210,00 EUR | abgeschlossen | 26.03.2025 09:43 | SO-27322 | Fehlt in Abrechnung | -210,00 EUR (vorläufig) |
| D-013 | 🟠 Mittel | B | 1048 | bpay_f44286b855 | 145,00 EUR | abgeschlossen | 04.03.2025 13:44 | SO-27336 | Mehrfach in Datenbank | nicht bestimmbar (betroffen: 145,00 EUR) |
| D-018 | 🟠 Mittel | A | 1026 | — | 64,00 EUR | abgeschlossen | 12.03.2025 08:19 | SO-27182 | Fehlt in Abrechnung | -64,00 EUR |
| D-019 | 🟠 Mittel | A | 1024 | ATX-67928316 | 42,00 EUR | abgeschlossen | 02.03.2025 17:09 | SO-27168 | Fehlt in Abrechnung | -42,00 EUR |
| D-020 | 🟠 Mittel | A | 1025 | ATX-54461448 | 120,00 EUR | ausstehend | 13.03.2025 05:03 | SO-27175 | Fehlt in Abrechnung | ±0 |
| D-021 | 🟡 Niedrig | A | 1028 | ATX-31598691 | 75,00 EUR | abgeschlossen | 31.03.2025 12:00 | SO-27196 | Noch nicht fällig | nicht bestimmbar (betroffen: 75,00 EUR) |

### 3.2 Nur in der Abrechnung (5)

| Nr. | Priorität | Anbieter | ID | Referenz | Betrag | Status | Zeitpunkt | Bestellung | Befund | Auswirkung |
|---|---|---|---|---|---|---|---|---|---|---|
| D-005 | 🔴 Hoch | A | ATX-85523351 | ATX-85523351 | 640,00 EUR | abgeschlossen | 04.03.2025 22:19 |  | Fehlt in Datenbank | +640,00 EUR |
| D-011 | 🟠 Mittel | A | ATX-49497139 | ATX-49497139 | 310,00 EUR | abgeschlossen | 18.03.2025 20:41 |  | Mehrfach in Abrechnung | nicht bestimmbar (betroffen: 310,00 EUR) |
| D-014 | 🟠 Mittel | A | atx84860779 | atx84860779 | 95,00 EUR | abgeschlossen | 08.03.2025 11:03 |  | Mehrfach in Abrechnung, Mögliche ID-Kollision | nicht bestimmbar (betroffen: 95,00 EUR) |
| D-016 | 🟠 Mittel | B | bpay_5e5b78866a | bpay_5e5b78866a | 88,00 EUR | abgeschlossen | 26.03.2025 10:54 |  | Fehlt in Datenbank | +88,00 EUR |
| D-023 | 🟡 Niedrig | A | ATX-47573247 | ATX-47573247 | 19,99 EUR | abgeschlossen | 17.03.2025 09:51 |  | Fehlt in Datenbank | +19,99 EUR |

## 4. Zugeordnete Transaktionen (41)

| Anbieter | DB-ID | Anbieter-ID | Zuordnung | Betrag (DB) | Status (DB / Anbieter) | Ergebnis |
|---|---|---|---|---|---|---|
| A | 1011 | ATX-35413626 | exakt | 250,00 USD | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1016 | ATX-42675569 | exakt | 899,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-015 |
| A | 1008 | ATX-65217433 | exakt | 310,75 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1047 | bpay_f44286b855 | exakt | 145,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1001 | ATX-84860229 | exakt | 49,90 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1014 | ATX-89949668 | exakt | 27,90 EUR | ausstehend / ausstehend | ✅ in Ordnung |
| A | 1006 | ATX-15818526 | exakt | 560,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1041 | bpay_e8ae863265 | exakt | 129,00 EUR | erstattet / erstattet | ✅ in Ordnung |
| A | 1030 | ATX-84860779 | exakt | 95,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1032 | TX-85695696 | unscharf (95%) | 220,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-024 |
| B | 1042 | bpay_5dbdcb245d | exakt | 200,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-007 |
| B | 1038 | bpay_92dad0400c | exakt | 775,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1044 | bpay_82ee6d74f5 | exakt | 1.150,00 EUR | abgeschlossen / fehlgeschlagen | ⚠ siehe D-004 |
| B | 1034 | bpay_928dda3e06 | exakt | 1.480,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1002 | ATX-74103220 | exakt | 120,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1020 | ATX-87490478 | exakt | 2.500,00 EUR | abgeschlossen / erstattet | ⚠ siehe D-002 |
| A | 1010 | ATX-18968577 | exakt | 7,50 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1015 | ATX-36588931 | exakt | 1.250,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-022 |
| B | 1037 | bpay_3434fc75e9 | exakt | 9,99 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1045 | bpay_cc50b8a435 | exakt | 330,00 EUR | abgeschlossen / unbekannt | ⚠ siehe D-010 |
| A | 1004 | ATX-86465021 | exakt | 15,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1040 | bpay_2cf2fad60e | exakt | 99,00 USD | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1029 | ATX-49497139 | exakt | 310,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1003 | ATX-10060049 | exakt | 1.234,56 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1007 | ATX-38394179 | exakt | 23,45 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1012 | ATX-40592523 | exakt | 64,00 EUR | erstattet / erstattet | ✅ in Ordnung |
| A | 1005 | ATX-61364363 | exakt | 89,99 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1036 | bpay_810645cae8 | exakt | 210,50 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1049 | bpay_748d856c7 | unscharf (98%) | 62,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-027 |
| B | 1039 | bpay_9518300ccc | exakt | 15.800 JPY | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1019 | ATX-47281038 | exakt | 75,00 EUR | ausstehend / abgeschlossen | ⚠ siehe D-017 |
| B | 1043 | bpay_9a3aad9bb6 | exakt | 75,50 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-025 |
| A | 1022 | ATX-81349318 | exakt | 500,00 EUR | abgeschlossen / ausstehend | ⚠ siehe D-006 |
| A | 1018 | ATX-21622603 | exakt | 349,90 EUR | abgeschlossen / fehlgeschlagen | ⚠ siehe D-009 |
| B | 1035 | bpay_57d35cae17 | exakt | 56,20 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1013 | ATX-57576259 | exakt | 18,00 EUR | fehlgeschlagen / fehlgeschlagen | ✅ in Ordnung |
| A | 1021 | ATX-53501687 | exakt | 33,00 EUR | ausstehend / fehlgeschlagen | ⚠ siehe D-026 |
| A | 1031 | ATX-4700150O | unscharf (94%) | 180,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-028 |
| B | 1033 | bpay_e859ddeb38 | exakt | 35,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1017 | ATX-28268772 | exakt | 12.000,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-001 |
| A | 1009 | ATX-13740587 | exakt | 999,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |

## 5. Importprobleme

Diese Zeilen konnten nicht (sauber) gelesen werden und müssen manuell geprüft werden – *Fehler* bedeutet: Zeile **nicht** abgeglichen.

| Quelle | Position | Art | Meldung |
|---|---|---|---|
| provider_a | Zeile 3 | Fehler | Zeile übersprungen: ungültiger Betrag: 'n/a' |
| provider_b | transactions[0] | Warnung | unbekannter Status 'chargeback_initiated' – als UNKNOWN übernommen |
| provider_b | transactions[15] | Fehler | Eintrag übersprungen: Feld 'id' fehlt |

## 6. Methodik und Annahmen

- **Modell:** Die Quellen sind Zustands-Schnappschüsse einer Transaktion (kein Ereignisjournal); verglichen werden Brutto-Beträge.
- **Zuordnung exakt:** gleicher Anbieter und gleiche Referenz nach der ID-Regel des Anbieters (A: ohne Groß-/Kleinschreibung und Trennzeichen, B: exakt). Rohwerte bleiben erhalten.
- **Zuordnung unscharf** (nur für Reste): gleicher Anbieter und Währung, Zeitfenster ±3 Tage, Referenz-Ähnlichkeit ≥ 80% (≥ 92%, wenn auch der Betrag abweicht), Gesamtscore ≥ 80% (60 % Referenz, 30 % Betrag, 10 % Zeit). Solche Paare erscheinen immer als „Unscharfe Zuordnung“ zur Bestätigung.
- **Verbuchter Betrag:** abgeschlossen = Betrag; ausstehend, fehlgeschlagen, erstattet = 0; unbekannter Status = **nicht bestimmt** (keine Auswirkung).
- **Auswirkung** = verbuchter Betrag Anbieter − verbuchter Betrag Datenbank, je Währung, ohne Umrechnung. Nicht bestimmbar bei Duplikaten, ID-Kollisionen, Währungsabweichung, unbekanntem Status, unlesbarer Quellzeile und Buchungen innerhalb der Frist – dort wird nur der betroffene Betrag ausgewiesen.
- **Fälligkeit:** überfällig, wenn Stichtag > Buchungszeit + 3 Tage; Zeiten sind UTC.
- **Betragstoleranz:** 0,00 (Dezimalvergleich, nie Fließkomma).
