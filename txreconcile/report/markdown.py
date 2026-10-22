"""Markdown-Bericht (deutsch): Kennzahlen, priorisierte Abweichungen, (nicht) zugeordnete Transaktionen."""
from __future__ import annotations

from decimal import Decimal

from ..formatting import (KIND_LABELS, PRIORITY_ICONS, PRIORITY_LABELS, STATUS_LABELS, fmt_impact, fmt_money,
                          fmt_number)
from ..models import Discrepancy, IssueKind, Priority, Transaction
from ..reconcile import ReconciliationResult

_UNMATCHED_KINDS = {IssueKind.MISSING_IN_PROVIDER, IssueKind.MISSING_IN_DB,
                    IssueKind.DUPLICATE_IN_DB, IssueKind.DUPLICATE_IN_PROVIDER}


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _tx(tx: Transaction | None) -> str:
    if tx is None:
        return "—"
    return f"{fmt_money(tx.amount, tx.currency)} · {STATUS_LABELS[tx.status]}"


def _impact_cells(totals: dict[str, Decimal], signed: bool = True) -> str:
    return fmt_impact(totals, signed)


def render_markdown(result: ReconciliationResult) -> str:
    s = result.summary
    out: list[str] = []
    add = out.append

    add("# Transaktionsabgleich – Bericht\n")
    add(f"*Erstellt am {result.generated_at:%d.%m.%Y %H:%M} UTC · Quellen: "
        + ", ".join(f"`{src.path.replace(chr(92), '/').split('/')[-1]}`" for src in result.sources) + "*\n")

    # ---- 1. Zusammenfassung ---------------------------------------------------
    high = s.by_priority.get(Priority.HIGH, 0)
    add("## 1. Zusammenfassung\n")
    add(f"**{s.matched} Paare zugeordnet** ({s.exact} exakt, {s.fuzzy} unscharf), davon {s.clean_matches} ohne "
        f"Abweichung. **{s.discrepancy_count} Abweichungen**, davon **{high} mit hoher Priorität**. "
        f"Nettoauswirkung (Abrechnung − Datenbank): **{_impact_cells(s.net_impact)}**; "
        f"Bruttovolumen der Abweichungen: {_impact_cells(s.gross_impact, signed=False)}.\n")

    add("### Kennzahlen\n")
    add(_table(["Kennzahl", "Wert"], [
        ["Datensätze interne Datenbank", s.internal_total],
        ["Datensätze Abrechnungen (A + B)", s.provider_total],
        ["Zugeordnete Paare", f"{s.matched} ({s.exact} exakt · {s.fuzzy} unscharf)"],
        ["Zuordnungsquote (Datensätze beider Seiten)", f"{s.match_rate:.1%}".replace(".", ",")],
        ["Davon fehlerfrei (ohne Abweichung)", f"{s.clean_matches} ({s.clean_rate:.1%})".replace(".", ",")],
        ["Nur in Datenbank (fehlt in Abrechnung)", s.unmatched_internal],
        ["Nur in Abrechnung (fehlt in Datenbank)", s.unmatched_provider],
        ["Duplikate (überzählige Einträge)", s.duplicates],
        ["Abweichungen gesamt", s.discrepancy_count],
        ["Importprobleme (Zeilen übersprungen / Warnungen)",
         f"{sum(len(x.errors) for x in result.sources)} / {sum(len(x.warnings) for x in result.sources)}"],
    ]))

    add("\n### Nach Anbieter\n")
    add(_table(
        ["Anbieter", "DB", "Abrechnung", "Zugeordnet", "Nur DB", "Nur Abrechnung", "Duplikate", "Abweichungen",
         "Auswirkung"],
        [[p.provider, p.internal_total, p.provider_total, p.matched, p.missing_in_provider, p.missing_in_db,
          p.duplicates, p.discrepancies, _impact_cells(p.impact)] for p in s.providers]))

    add("\n### Abweichungen nach Hauptbefund\n")
    add("Jede Abweichung wird genau einmal gezählt (Hauptbefund = schwerster Einzelbefund); "
        "ein Datensatz kann zusätzliche Nebenbefunde haben.\n")
    add(_table(["Befund", "Anzahl", "Auswirkung (Abrechnung − DB)"],
               [[KIND_LABELS[kind], st.count, _impact_cells(st.impact)] for kind, st in s.by_kind.items()]))

    add("\n### Nach Priorität\n")
    add(_table(["Priorität", "Anzahl", "Bedeutung"], [
        [f"{PRIORITY_ICONS[p]} {PRIORITY_LABELS[p]}", s.by_priority.get(p, 0), meaning] for p, meaning in (
            (Priority.HIGH, f"Auswirkung ≥ {fmt_number(result.config.high_threshold)} EUR oder Währungskonflikt – "
                            "sofort klären"),
            (Priority.MEDIUM, f"Auswirkung ≥ {fmt_number(result.config.medium_threshold)} EUR – zeitnah klären"),
            (Priority.LOW, "geringe oder keine finanzielle Wirkung – im Regelprozess prüfen"))]))

    # ---- 2. Priorisierte Abweichungen -------------------------------------------
    numbers = {id(d): n for n, d in enumerate(result.discrepancies, 1)}
    add("\n## 2. Priorisierte Abweichungen\n")
    add("Sortiert nach Priorität, dann nach absoluter finanzieller Auswirkung. "
        "Die Nummern (D-xxx) sind in `discrepancies.csv` und `report.json` identisch.\n")
    for priority in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
        items = [d for d in result.discrepancies if d.priority is priority]
        if not items:
            continue
        add(f"### {PRIORITY_ICONS[priority]} Priorität {PRIORITY_LABELS[priority]} ({len(items)})\n")
        add(_table(["Nr.", "Befund", "Anbieter", "DB-ID", "Anbieter-ID", "Datenbank", "Anbieter", "Auswirkung",
                    "Empfohlene Maßnahme"],
                   [_discrepancy_row(numbers[id(d)], d) for d in items]))
        add("")

    # ---- 3. Nicht zugeordnete Transaktionen --------------------------------------
    only_db = [d for d in result.discrepancies if d.internal and not d.provider]
    only_provider = [d for d in result.discrepancies if d.provider and not d.internal]
    add("## 3. Nicht zugeordnete Transaktionen\n")
    add(f"### 3.1 Nur in der Datenbank – fehlt in der Abrechnung ({len(only_db)})\n")
    add(_unmatched_table(only_db, numbers, "internal") if only_db else "_Keine._")
    add(f"\n### 3.2 Nur in der Abrechnung – fehlt in der Datenbank ({len(only_provider)})\n")
    add(_unmatched_table(only_provider, numbers, "provider") if only_provider else "_Keine._")

    # ---- 4. Zugeordnete Transaktionen --------------------------------------------
    flagged = result.flagged_matches
    matches = result.sorted_matches()
    limit = result.config.max_matched_rows
    add(f"\n## 4. Zugeordnete Transaktionen ({len(matches)})\n")
    rows = []
    for m in matches[:limit]:
        item = flagged.get((m.internal.record_id, m.provider.record_id))
        rows.append([
            m.internal.provider, m.internal.record_id, m.provider.record_id,
            "exakt" if m.method == "exact" else f"unscharf ({m.confidence:.0%})",
            fmt_money(m.internal.amount, m.internal.currency),
            f"{STATUS_LABELS[m.internal.status]} / {STATUS_LABELS[m.provider.status]}",
            f"⚠ siehe D-{numbers[id(item)]:03d}" if item else "✅ in Ordnung",
        ])
    add(_table(["Anbieter", "DB-ID", "Anbieter-ID", "Zuordnung", "Betrag (DB)", "Status (DB / Anbieter)",
                "Ergebnis"], rows))
    if len(matches) > limit:
        add(f"\n_… {len(matches) - limit} weitere Zeilen: siehe `matched.csv` bzw. `report.json`._")

    # ---- 5. Importprobleme -----------------------------------------------------------
    add("\n## 5. Importprobleme\n")
    if result.import_issues:
        add("Diese Zeilen konnten nicht (sauber) gelesen werden und müssen manuell geprüft werden – "
            "*Fehler* bedeutet: Zeile **nicht** abgeglichen.\n")
        add(_table(["Quelle", "Position", "Art", "Meldung"],
                   [[i.source, i.location, "Fehler" if i.severity == "error" else "Warnung", i.message]
                    for i in result.import_issues]))
    else:
        add("_Keine._")

    # ---- 6. Methodik -------------------------------------------------------------------
    c = result.config
    add("\n## 6. Methodik und Annahmen\n")
    add("- **Zuordnung exakt:** gleicher Anbieter und gleiche Referenz nach Normalisierung "
        "(Groß-/Kleinschreibung, Leerzeichen und Sonderzeichen werden ignoriert).")
    if c.fuzzy_enabled:
        add(f"- **Zuordnung unscharf** (nur für Reste): gleicher Anbieter und Währung, Zeitfenster "
            f"±{c.fuzzy_time_window.days} Tage, Referenz-Ähnlichkeit ≥ {c.fuzzy_min_ref_similarity:.0%} "
            f"(≥ {c.fuzzy_min_ref_similarity_if_amount_differs:.0%}, wenn auch der Betrag abweicht), "
            f"Gesamtscore ≥ {c.fuzzy_min_score:.0%} (60 % Referenz, 30 % Betrag, 10 % Zeit). "
            "Solche Paare erscheinen immer als „Unscharfe Zuordnung“ zur Bestätigung.")
    else:
        add("- **Unscharfe Zuordnung:** deaktiviert.")
    add("- **Finanzielle Auswirkung** = verbuchter Betrag Anbieter − verbuchter Betrag Datenbank, je Währung; "
        "verbucht ist nur der Status *abgeschlossen*. Währungen werden nicht verrechnet.")
    add(f"- **Priorität:** Hoch ab {fmt_number(c.high_threshold)} EUR, Mittel ab {fmt_number(c.medium_threshold)} EUR "
        "(Umrechnung nur für die Priorisierung mit statischen Kursen); Währungskonflikte immer hoch.")
    add(f"- **Betragstoleranz:** {fmt_number(c.amount_tolerance)} (Beträge werden als Dezimalzahlen verglichen, nie als Fließkommazahl).")
    return "\n".join(out) + "\n"


def _discrepancy_row(number: int, item: Discrepancy) -> list[object]:
    labels = ", ".join(KIND_LABELS[k] for k in item.kinds)
    return [
        f"D-{number:03d}", f"**{labels}**<br>{item.description}", item.provider_code,
        item.internal.record_id if item.internal else "—",
        item.provider.record_id if item.provider else "—",
        _tx(item.internal), _tx(item.provider), fmt_impact(item.impact), item.action,
    ]


def _unmatched_table(items: list[Discrepancy], numbers: dict[int, int], side: str) -> str:
    rows = []
    for d in items:
        tx = d.internal if side == "internal" else d.provider
        extra = tx.note if side == "internal" and tx.note else ""
        rows.append([
            f"D-{numbers[id(d)]:03d}", f"{PRIORITY_ICONS[d.priority]} {PRIORITY_LABELS[d.priority]}",
            tx.provider, tx.record_id, tx.reference or "—", fmt_money(tx.amount, tx.currency),
            STATUS_LABELS[tx.status], tx.timestamp.strftime("%d.%m.%Y %H:%M"),
            extra, ", ".join(KIND_LABELS[k] for k in d.kinds), fmt_impact(d.impact),
        ])
    return _table(["Nr.", "Priorität", "Anbieter", "ID", "Referenz", "Betrag", "Status", "Zeitpunkt",
                   "Bestellung", "Befund", "Auswirkung"], rows)
