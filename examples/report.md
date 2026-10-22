# Transaktionsabgleich – Bericht

*Erstellt am 22.10.2026 20:09 UTC · Quellen: `internal.db`, `provider_a.csv`, `provider_b.json`*

## 1. Zusammenfassung

**40 Paare zugeordnet** (37 exakt, 3 unscharf), davon 25 ohne Abweichung. **26 Abweichungen**, davon **7 mit hoher Priorität**. Nettoauswirkung (Abrechnung − Datenbank): **-17.358,91 EUR / +200,00 USD**; Bruttovolumen der Abweichungen: 19.804,89 EUR / 200,00 USD.

### Kennzahlen

| Kennzahl | Wert |
|---|---|
| Datensätze interne Datenbank | 47 |
| Datensätze Abrechnungen (A + B) | 44 |
| Zugeordnete Paare | 40 (37 exakt · 3 unscharf) |
| Zuordnungsquote (Datensätze beider Seiten) | 87,9% |
| Davon fehlerfrei (ohne Abweichung) | 25 (54,9%) |
| Nur in Datenbank (fehlt in Abrechnung) | 6 |
| Nur in Abrechnung (fehlt in Datenbank) | 3 |
| Duplikate (überzählige Einträge) | 2 |
| Abweichungen gesamt | 26 |
| Importprobleme (Zeilen übersprungen / Warnungen) | 2 / 1 |

### Nach Anbieter

| Anbieter | DB | Abrechnung | Zugeordnet | Nur DB | Nur Abrechnung | Duplikate | Abweichungen | Auswirkung |
|---|---|---|---|---|---|---|---|---|
| A | 30 | 28 | 25 | 5 | 2 | 1 | 18 | -15.393,91 EUR |
| B | 17 | 16 | 15 | 1 | 1 | 1 | 8 | -1.965,00 EUR / +200,00 USD |

### Abweichungen nach Hauptbefund

Jede Abweichung wird genau einmal gezählt (Hauptbefund = schwerster Einzelbefund); ein Datensatz kann zusätzliche Nebenbefunde haben.

| Befund | Anzahl | Auswirkung (Abrechnung − DB) |
|---|---|---|
| Währungsabweichung | 1 | -200,00 EUR / +200,00 USD |
| Fehlt in Abrechnung | 6 | -2.526,00 EUR |
| Fehlt in Datenbank | 3 | +747,99 EUR |
| Duplikat in Datenbank | 1 | -145,00 EUR |
| Duplikat in Abrechnung | 1 | +310,00 EUR |
| Statusabweichung | 7 | -4.754,90 EUR |
| Betragsabweichung | 5 | -10.791,00 EUR |
| Unscharfe Zuordnung | 2 | ±0 |

### Nach Priorität

| Priorität | Anzahl | Bedeutung |
|---|---|---|
| 🔴 Hoch | 7 | Auswirkung ≥ 500,00 EUR oder Währungskonflikt – sofort klären |
| 🟠 Mittel | 10 | Auswirkung ≥ 50,00 EUR – zeitnah klären |
| 🟡 Niedrig | 9 | geringe oder keine finanzielle Wirkung – im Regelprozess prüfen |

## 2. Priorisierte Abweichungen

Sortiert nach Priorität, dann nach absoluter finanzieller Auswirkung. Die Nummern (D-xxx) sind in `discrepancies.csv` und `report.json` identisch.

### 🔴 Priorität Hoch (7)

| Nr. | Befund | Anbieter | DB-ID | Anbieter-ID | Datenbank | Anbieter | Auswirkung | Empfohlene Maßnahme |
|---|---|---|---|---|---|---|---|---|
| D-001 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 12.000,00 EUR vs. Anbieter 1.200,00 EUR (Differenz -10.800,00 EUR). | A | 1017 | ATX-28268772 | 12.000,00 EUR · abgeschlossen | 1.200,00 EUR · abgeschlossen | -10.800,00 EUR | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-002 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter erstattet. | A | 1020 | ATX-87490478 | 2.500,00 EUR · abgeschlossen | 2.500,00 EUR · erstattet | -2.500,00 EUR | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-003 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 1.800,00 EUR (abgeschlossen) vom 04.03.2025 20:19; Abrechnung von Anbieter A enthält keinen Eintrag. | A | 1023 | — | 1.800,00 EUR · abgeschlossen | — | -1.800,00 EUR | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-004 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter fehlgeschlagen. | B | 1042 | bpay_9a3aad9bb6 | 1.150,00 EUR · abgeschlossen | 1.150,00 EUR · fehlgeschlagen | -1.150,00 EUR | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-005 | **Fehlt in Datenbank**<br>Nur in der Abrechnung von Anbieter A: 640,00 EUR (abgeschlossen) vom 04.03.2025 22:19; keine passende Buchung in der Datenbank. | A | — | ATX-85523351 | — | 640,00 EUR · abgeschlossen | +640,00 EUR | Geldeingang dem passenden Vorgang zuordnen und nachbuchen. |
| D-006 | **Statusabweichung, Betragsabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter ausstehend. Betrag weicht ab: Datenbank 500,00 EUR vs. Anbieter 450,00 EUR (Differenz -50,00 EUR). | A | 1022 | ATX-81349318 | 500,00 EUR · abgeschlossen | 450,00 EUR · ausstehend | -500,00 EUR | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-007 | **Währungsabweichung**<br>Währung weicht ab: Datenbank 200,00 EUR vs. Anbieter 200,00 USD; Beträge sind nicht vergleichbar. | B | 1040 | bpay_e8ae863265 | 200,00 EUR · abgeschlossen | 200,00 USD · abgeschlossen | -200,00 EUR / +200,00 USD | Währung der Buchung gegen den Beleg prüfen und Fehlbuchung korrigieren. |

### 🟠 Priorität Mittel (10)

| Nr. | Befund | Anbieter | DB-ID | Anbieter-ID | Datenbank | Anbieter | Auswirkung | Empfohlene Maßnahme |
|---|---|---|---|---|---|---|---|---|
| D-008 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 410,00 EUR (abgeschlossen) vom 27.03.2025 02:53; Abrechnung von Anbieter A enthält keinen Eintrag. Die Abrechnungsdatei enthält einen unlesbaren Datensatz mit dieser Referenz (siehe Importprobleme). | A | 1027 | — | 410,00 EUR · abgeschlossen | — | -410,00 EUR | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-009 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter fehlgeschlagen. | A | 1018 | ATX-21622603 | 349,90 EUR · abgeschlossen | 349,90 EUR · fehlgeschlagen | -349,90 EUR | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-010 | **Statusabweichung**<br>Status weicht ab: Datenbank abgeschlossen vs. Anbieter unbekannt ('chargeback_initiated'). | B | 1043 | bpay_82ee6d74f5 | 330,00 EUR · abgeschlossen | 330,00 EUR · unbekannt | -330,00 EUR | Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen. |
| D-011 | **Duplikat in Abrechnung**<br>Doppelte Abrechnung: Referenz 'ATX-54450551' kommt mehrfach in der Abrechnung vor; 310,00 EUR ist bereits der DB-ID 1028 zugeordnet. | A | — | ATX-54450551 | — | 310,00 EUR · abgeschlossen | +310,00 EUR | Doppelte Abrechnung beim Anbieter reklamieren (mögliche Doppelbelastung). |
| D-012 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 210,00 EUR (abgeschlossen) vom 12.03.2025 09:53; Abrechnung von Anbieter B enthält keinen Eintrag. | B | 1044 | — | 210,00 EUR · abgeschlossen | — | -210,00 EUR | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-013 | **Duplikat in Datenbank**<br>Doppelbuchung: Referenz 'bpay_84e7808d1c' ist mehrfach in der Datenbank; 145,00 EUR ist bereits dem Anbietereintrag zugeordnet (DB-ID 1045). | B | 1046 | — | 145,00 EUR · abgeschlossen | — | -145,00 EUR | Doppelbuchung prüfen und die überzählige Buchung stornieren. |
| D-014 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 899,00 EUR vs. Anbieter 989,00 EUR (Differenz +90,00 EUR). | A | 1016 | ATX-42675569 | 899,00 EUR · abgeschlossen | 989,00 EUR · abgeschlossen | +90,00 EUR | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-015 | **Fehlt in Datenbank**<br>Nur in der Abrechnung von Anbieter B: 88,00 EUR (abgeschlossen) vom 18.03.2025 11:16; keine passende Buchung in der Datenbank. | B | — | bpay_e2028c88e3 | — | 88,00 EUR · abgeschlossen | +88,00 EUR | Geldeingang dem passenden Vorgang zuordnen und nachbuchen. |
| D-016 | **Statusabweichung**<br>Status weicht ab: Datenbank ausstehend vs. Anbieter abgeschlossen. | A | 1019 | ATX-47281038 | 75,00 EUR · ausstehend | 75,00 EUR · abgeschlossen | +75,00 EUR | Status in der Datenbank aktualisieren (Zahlung ist beim Anbieter abgeschlossen). |
| D-017 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 64,00 EUR (abgeschlossen) vom 12.03.2025 08:19; Abrechnung von Anbieter A enthält keinen Eintrag. Es ist keine Provider-Referenz hinterlegt. | A | 1026 | — | 64,00 EUR · abgeschlossen | — | -64,00 EUR | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |

### 🟡 Priorität Niedrig (9)

| Nr. | Befund | Anbieter | DB-ID | Anbieter-ID | Datenbank | Anbieter | Auswirkung | Empfohlene Maßnahme |
|---|---|---|---|---|---|---|---|---|
| D-018 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 1.250,00 EUR vs. Anbieter 1.205,00 EUR (Differenz -45,00 EUR). | A | 1015 | ATX-36588931 | 1.250,00 EUR · abgeschlossen | 1.205,00 EUR · abgeschlossen | -45,00 EUR | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-019 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 42,00 EUR (abgeschlossen) vom 02.03.2025 17:09; Abrechnung von Anbieter A enthält keinen Eintrag. | A | 1024 | — | 42,00 EUR · abgeschlossen | — | -42,00 EUR | Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren. |
| D-020 | **Fehlt in Datenbank**<br>Nur in der Abrechnung von Anbieter A: 19,99 EUR (abgeschlossen) vom 14.03.2025 22:09; keine passende Buchung in der Datenbank. | A | — | ATX-31598691 | — | 19,99 EUR · abgeschlossen | +19,99 EUR | Geldeingang dem passenden Vorgang zuordnen und nachbuchen. |
| D-021 | **Betragsabweichung**<br>Betrag weicht ab: Datenbank 75,50 EUR vs. Anbieter 57,50 EUR (Differenz -18,00 EUR). | B | 1041 | bpay_5dbdcb245d | 75,50 EUR · abgeschlossen | 57,50 EUR · abgeschlossen | -18,00 EUR | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. |
| D-022 | **Betragsabweichung, Unscharfe Zuordnung**<br>Betrag weicht ab: Datenbank 220,00 EUR vs. Anbieter 202,00 EUR (Differenz -18,00 EUR). Zuordnung über unscharfe Suche: Referenz 'ATX-47001509' (DB) ↔ 'TX-47001509' (Anbieter), Konfidenz 95%. | A | 1030 | TX-47001509 | 220,00 EUR · abgeschlossen | 202,00 EUR · abgeschlossen | -18,00 EUR | Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren. Zuordnung bestätigen und die Referenz in der Datenbank korrigieren. |
| D-023 | **Fehlt in Abrechnung**<br>Nur in der Datenbank: 120,00 EUR (ausstehend) vom 13.03.2025 05:03; Abrechnung von Anbieter A enthält keinen Eintrag. | A | 1025 | — | 120,00 EUR · ausstehend | — | ±0 | Buchung ist nicht abgeschlossen: nächste Abrechnung abwarten und erneut abgleichen. |
| D-024 | **Statusabweichung**<br>Status weicht ab: Datenbank ausstehend vs. Anbieter fehlgeschlagen. | A | 1021 | ATX-53501687 | 33,00 EUR · ausstehend | 33,00 EUR · fehlgeschlagen | ±0 | Status mit dem Anbieter klären; derzeit keine finanzielle Wirkung. |
| D-025 | **Unscharfe Zuordnung**<br>Zuordnung über unscharfe Suche: Referenz 'bpay_4253720ec4' (DB) ↔ 'bpay_425720ec4' (Anbieter), Konfidenz 98%. | B | 1047 | bpay_425720ec4 | 62,00 EUR · abgeschlossen | 62,00 EUR · abgeschlossen | ±0 | Zuordnung bestätigen und die Referenz in der Datenbank korrigieren. |
| D-026 | **Unscharfe Zuordnung**<br>Zuordnung über unscharfe Suche: Referenz 'ATX-20133979' (DB) ↔ 'ATX-2013397O' (Anbieter), Konfidenz 94%. | A | 1029 | ATX-2013397O | 180,00 EUR · abgeschlossen | 180,00 EUR · abgeschlossen | ±0 | Zuordnung bestätigen und die Referenz in der Datenbank korrigieren. |

## 3. Nicht zugeordnete Transaktionen

### 3.1 Nur in der Datenbank – fehlt in der Abrechnung (7)

| Nr. | Priorität | Anbieter | ID | Referenz | Betrag | Status | Zeitpunkt | Bestellung | Befund | Auswirkung |
|---|---|---|---|---|---|---|---|---|---|---|
| D-003 | 🔴 Hoch | A | 1023 | ATX-85523350 | 1.800,00 EUR | abgeschlossen | 04.03.2025 20:19 | SO-27161 | Fehlt in Abrechnung | -1.800,00 EUR |
| D-008 | 🟠 Mittel | A | 1027 | ATX-83009462 | 410,00 EUR | abgeschlossen | 27.03.2025 02:53 | SO-27189 | Fehlt in Abrechnung | -410,00 EUR |
| D-012 | 🟠 Mittel | B | 1044 | bpay_cc50b8a435 | 210,00 EUR | abgeschlossen | 12.03.2025 09:53 | SO-27308 | Fehlt in Abrechnung | -210,00 EUR |
| D-013 | 🟠 Mittel | B | 1046 | bpay_84e7808d1c | 145,00 EUR | abgeschlossen | 18.03.2025 16:22 | SO-27322 | Duplikat in Datenbank | -145,00 EUR |
| D-017 | 🟠 Mittel | A | 1026 | — | 64,00 EUR | abgeschlossen | 12.03.2025 08:19 | SO-27182 | Fehlt in Abrechnung | -64,00 EUR |
| D-019 | 🟡 Niedrig | A | 1024 | ATX-67928316 | 42,00 EUR | abgeschlossen | 02.03.2025 17:09 | SO-27168 | Fehlt in Abrechnung | -42,00 EUR |
| D-023 | 🟡 Niedrig | A | 1025 | ATX-54461448 | 120,00 EUR | ausstehend | 13.03.2025 05:03 | SO-27175 | Fehlt in Abrechnung | ±0 |

### 3.2 Nur in der Abrechnung – fehlt in der Datenbank (4)

| Nr. | Priorität | Anbieter | ID | Referenz | Betrag | Status | Zeitpunkt | Bestellung | Befund | Auswirkung |
|---|---|---|---|---|---|---|---|---|---|---|
| D-005 | 🔴 Hoch | A | ATX-85523351 | ATX-85523351 | 640,00 EUR | abgeschlossen | 04.03.2025 22:19 |  | Fehlt in Datenbank | +640,00 EUR |
| D-011 | 🟠 Mittel | A | ATX-54450551 | ATX-54450551 | 310,00 EUR | abgeschlossen | 15.03.2025 14:54 |  | Duplikat in Abrechnung | +310,00 EUR |
| D-015 | 🟠 Mittel | B | bpay_e2028c88e3 | bpay_e2028c88e3 | 88,00 EUR | abgeschlossen | 18.03.2025 11:16 |  | Fehlt in Datenbank | +88,00 EUR |
| D-020 | 🟡 Niedrig | A | ATX-31598691 | ATX-31598691 | 19,99 EUR | abgeschlossen | 14.03.2025 22:09 |  | Fehlt in Datenbank | +19,99 EUR |

## 4. Zugeordnete Transaktionen (40)

| Anbieter | DB-ID | Anbieter-ID | Zuordnung | Betrag (DB) | Status (DB / Anbieter) | Ergebnis |
|---|---|---|---|---|---|---|
| A | 1011 | ATX-35413626 | exakt | 250,00 USD | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1016 | ATX-42675569 | exakt | 899,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-014 |
| A | 1008 | ATX-65217433 | exakt | 310,75 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1047 | bpay_425720ec4 | unscharf (98%) | 62,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-025 |
| A | 1001 | ATX-84860229 | exakt | 49,90 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1014 | ATX-89949668 | exakt | 27,90 EUR | ausstehend / ausstehend | ✅ in Ordnung |
| A | 1006 | ATX-15818526 | exakt | 560,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1040 | bpay_e8ae863265 | exakt | 200,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-007 |
| A | 1029 | ATX-2013397O | unscharf (94%) | 180,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-026 |
| B | 1031 | bpay_a39060ca11 | exakt | 35,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1041 | bpay_5dbdcb245d | exakt | 75,50 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-021 |
| B | 1037 | bpay_92dad0400c | exakt | 15.800 JPY | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1043 | bpay_82ee6d74f5 | exakt | 330,00 EUR | abgeschlossen / unbekannt | ⚠ siehe D-010 |
| B | 1033 | bpay_928dda3e06 | exakt | 56,20 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1002 | ATX-74103220 | exakt | 120,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1020 | ATX-87490478 | exakt | 2.500,00 EUR | abgeschlossen / erstattet | ⚠ siehe D-002 |
| A | 1010 | ATX-18968577 | exakt | 7,50 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1015 | ATX-36588931 | exakt | 1.250,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-018 |
| B | 1036 | bpay_3434fc75e9 | exakt | 775,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1004 | ATX-86465021 | exakt | 15,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1039 | bpay_2cf2fad60e | exakt | 129,00 EUR | erstattet / erstattet | ✅ in Ordnung |
| A | 1028 | ATX-54450551 | exakt | 310,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1045 | bpay_84e7808d1c | exakt | 145,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1003 | ATX-10060049 | exakt | 1.234,56 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1007 | ATX-38394179 | exakt | 23,45 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1012 | ATX-40592523 | exakt | 64,00 EUR | erstattet / erstattet | ✅ in Ordnung |
| A | 1005 | ATX-61364363 | exakt | 89,99 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1035 | bpay_810645cae8 | exakt | 9,99 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| B | 1038 | bpay_9518300ccc | exakt | 99,00 USD | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1019 | ATX-47281038 | exakt | 75,00 EUR | ausstehend / abgeschlossen | ⚠ siehe D-016 |
| B | 1042 | bpay_9a3aad9bb6 | exakt | 1.150,00 EUR | abgeschlossen / fehlgeschlagen | ⚠ siehe D-004 |
| A | 1022 | ATX-81349318 | exakt | 500,00 EUR | abgeschlossen / ausstehend | ⚠ siehe D-006 |
| A | 1018 | ATX-21622603 | exakt | 349,90 EUR | abgeschlossen / fehlgeschlagen | ⚠ siehe D-009 |
| B | 1034 | bpay_57d35cae17 | exakt | 210,50 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1013 | ATX-57576259 | exakt | 18,00 EUR | fehlgeschlagen / fehlgeschlagen | ✅ in Ordnung |
| A | 1021 | ATX-53501687 | exakt | 33,00 EUR | ausstehend / fehlgeschlagen | ⚠ siehe D-024 |
| A | 1030 | TX-47001509 | unscharf (95%) | 220,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-022 |
| B | 1032 | bpay_f9bae03d8f | exakt | 1.480,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |
| A | 1017 | ATX-28268772 | exakt | 12.000,00 EUR | abgeschlossen / abgeschlossen | ⚠ siehe D-001 |
| A | 1009 | ATX-13740587 | exakt | 999,00 EUR | abgeschlossen / abgeschlossen | ✅ in Ordnung |

## 5. Importprobleme

Diese Zeilen konnten nicht (sauber) gelesen werden und müssen manuell geprüft werden – *Fehler* bedeutet: Zeile **nicht** abgeglichen.

| Quelle | Position | Art | Meldung |
|---|---|---|---|
| provider_a | Zeile 4 | Fehler | Zeile übersprungen: ungültiger Betrag: 'n/a' |
| provider_b | transactions[3] | Fehler | Eintrag übersprungen: Feld 'id' fehlt |
| provider_b | transactions[14] | Warnung | unbekannter Status 'chargeback_initiated' – als UNKNOWN übernommen |

## 6. Methodik und Annahmen

- **Zuordnung exakt:** gleicher Anbieter und gleiche Referenz nach Normalisierung (Groß-/Kleinschreibung, Leerzeichen und Sonderzeichen werden ignoriert).
- **Zuordnung unscharf** (nur für Reste): gleicher Anbieter und Währung, Zeitfenster ±3 Tage, Referenz-Ähnlichkeit ≥ 80% (≥ 92%, wenn auch der Betrag abweicht), Gesamtscore ≥ 80% (60 % Referenz, 30 % Betrag, 10 % Zeit). Solche Paare erscheinen immer als „Unscharfe Zuordnung“ zur Bestätigung.
- **Finanzielle Auswirkung** = verbuchter Betrag Anbieter − verbuchter Betrag Datenbank, je Währung; verbucht ist nur der Status *abgeschlossen*. Währungen werden nicht verrechnet.
- **Priorität:** Hoch ab 500,00 EUR, Mittel ab 50,00 EUR (Umrechnung nur für die Priorisierung mit statischen Kursen); Währungskonflikte immer hoch.
- **Betragstoleranz:** 0,00 (Beträge werden als Dezimalzahlen verglichen, nie als Fließkommazahl).
