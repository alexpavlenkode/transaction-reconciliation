"""Erkennung und Bewertung von Abweichungen.

Finanzielle Auswirkung (zentrale Definition)
--------------------------------------------
Jede Seite hat einen *verbuchten Betrag*: der Betrag, wenn der Status ``COMPLETED`` ist, sonst 0
(ausstehend, fehlgeschlagen und erstattet bewegen kein Geld zu unseren Gunsten).

    Auswirkung = verbuchter Betrag (Anbieter) − verbuchter Betrag (Datenbank)    je Währung

* negativ: die Datenbank erwartet mehr Geld, als der Anbieter abrechnet (Fehlbetrag / Forderung offen)
* positiv: der Anbieter rechnet mehr ab, als die Datenbank kennt (nicht gebuchter Geldeingang)

Dieselbe Formel gilt für alle Abweichungsarten (fehlend, Betrag, Status, Duplikat, Währung).
Dadurch wird bei einem Datensatz mit *mehreren* Befunden die Auswirkung genau einmal gezählt.
Währungen werden nicht verrechnet; es gibt eine Auswirkung je Währung.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .config import ReconcileConfig
from .formatting import STATUS_LABELS, fmt_money, fmt_time
from .importers.base import ImportIssue
from .matching import MatchResult
from .models import Discrepancy, IssueKind, Match, Priority, Status, Transaction

_PROVIDER_OF_SOURCE = {"provider_a": "A", "provider_b": "B"}
_KIND_ORDER = {kind: n for n, kind in enumerate(IssueKind)}


def booked_amount(tx: Transaction | None) -> Decimal:
    """Verbuchter Betrag: nur abgeschlossene Zahlungen zählen."""
    return tx.amount if tx is not None and tx.status.settles else Decimal(0)


def net_impact(internal: Transaction | None, provider: Transaction | None) -> dict[str, Decimal]:
    impact: dict[str, Decimal] = defaultdict(Decimal)
    if provider is not None:
        impact[provider.currency] += booked_amount(provider)
    if internal is not None:
        impact[internal.currency] -= booked_amount(internal)
    return {currency: value for currency, value in impact.items() if value != 0}


def impact_worth(impact: dict[str, Decimal], config: ReconcileConfig) -> Decimal:
    """Größte absolute Auswirkung in EUR-Äquivalent – nur als Sortier-/Prioritätsmaß."""
    return max((abs(v) * config.fx_to_eur.get(c, Decimal(1)) for c, v in impact.items()), default=Decimal(0))


def prioritize(kinds: tuple[IssueKind, ...], impact: dict[str, Decimal], config: ReconcileConfig) -> Priority:
    if IssueKind.CURRENCY_MISMATCH in kinds:
        return Priority.HIGH                 # Beträge sind nicht vergleichbar -> immer manuell klären
    worth = impact_worth(impact, config)
    if worth >= config.high_threshold:
        return Priority.HIGH
    if worth >= config.medium_threshold:
        return Priority.MEDIUM
    return Priority.LOW


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def find_discrepancies(matching: MatchResult, config: ReconcileConfig,
                       import_issues: list[ImportIssue] | None = None) -> list[Discrepancy]:
    unreadable = {
        (_PROVIDER_OF_SOURCE.get(issue.source), issue.key)
        for issue in (import_issues or []) if issue.severity == "error" and issue.key
    }
    found: list[Discrepancy] = []

    for match in matching.matches:
        kinds = _compare(match, config)
        if kinds:
            found.append(_build(kinds, match.internal, match.provider, config, match=match))

    for tx in matching.unmatched_internal:
        hint = (tx.provider, tx.key) in unreadable
        found.append(_build((IssueKind.MISSING_IN_PROVIDER,), tx, None, config, unreadable_hint=hint))
    for tx in matching.unmatched_provider:
        found.append(_build((IssueKind.MISSING_IN_DB,), None, tx, config))
    for tx, original in matching.duplicate_internal:
        found.append(_build((IssueKind.DUPLICATE_IN_DB,), tx, None, config, match=original))
    for tx, original in matching.duplicate_provider:
        found.append(_build((IssueKind.DUPLICATE_IN_PROVIDER,), None, tx, config, match=original))

    found.sort(key=lambda d: (
        d.priority.rank, -impact_worth(d.impact, config), _KIND_ORDER[d.primary_kind],
        (d.internal or d.provider).timestamp, (d.internal or d.provider).record_id))
    return found


def _compare(match: Match, config: ReconcileConfig) -> tuple[IssueKind, ...]:
    internal, provider = match.internal, match.provider
    kinds: list[IssueKind] = []
    if internal.currency != provider.currency:
        kinds.append(IssueKind.CURRENCY_MISMATCH)        # Beträge verschiedener Währungen nie vergleichen
    elif abs(internal.amount - provider.amount) > config.amount_tolerance:
        kinds.append(IssueKind.AMOUNT_MISMATCH)
    if internal.status is not provider.status:
        kinds.append(IssueKind.STATUS_MISMATCH)
    if match.method == "fuzzy":
        kinds.append(IssueKind.REFERENCE_MISMATCH)
    return tuple(sorted(kinds, key=_KIND_ORDER.__getitem__))


def _build(kinds, internal, provider, config, *, match=None, unreadable_hint=False) -> Discrepancy:
    impact = net_impact(internal, provider)
    return Discrepancy(
        kinds=kinds, internal=internal, provider=provider, impact=impact,
        priority=prioritize(kinds, impact, config),
        description=" ".join(_describe(kind, internal, provider, match, unreadable_hint) for kind in kinds),
        action=" ".join(_action(kind, internal, provider) for kind in kinds),
        match=match,
    )


# ---------------------------------------------------------------------------
# Texte (deutsch, handlungsorientiert)
# ---------------------------------------------------------------------------

def _status_text(tx: Transaction) -> str:
    label = STATUS_LABELS[tx.status]
    return f"{label} ('{tx.raw_status}')" if tx.status is Status.UNKNOWN else label


def _describe(kind, internal, provider, match, unreadable_hint) -> str:
    if kind is IssueKind.MISSING_IN_PROVIDER:
        text = (f"Nur in der Datenbank: {fmt_money(internal.amount, internal.currency)} "
                f"({_status_text(internal)}) vom {fmt_time(internal.timestamp)}; "
                f"Abrechnung von Anbieter {internal.provider} enthält keinen Eintrag.")
        if not internal.reference:
            text += " Es ist keine Provider-Referenz hinterlegt."
        if unreadable_hint:
            text += " Die Abrechnungsdatei enthält einen unlesbaren Datensatz mit dieser Referenz (siehe Importprobleme)."
        return text
    if kind is IssueKind.MISSING_IN_DB:
        return (f"Nur in der Abrechnung von Anbieter {provider.provider}: "
                f"{fmt_money(provider.amount, provider.currency)} ({_status_text(provider)}) "
                f"vom {fmt_time(provider.timestamp)}; keine passende Buchung in der Datenbank.")
    if kind is IssueKind.AMOUNT_MISMATCH:
        diff = provider.amount - internal.amount
        return (f"Betrag weicht ab: Datenbank {fmt_money(internal.amount, internal.currency)} vs. "
                f"Anbieter {fmt_money(provider.amount, provider.currency)} "
                f"(Differenz {fmt_money(diff, internal.currency, signed=True)}).")
    if kind is IssueKind.STATUS_MISMATCH:
        return f"Status weicht ab: Datenbank {_status_text(internal)} vs. Anbieter {_status_text(provider)}."
    if kind is IssueKind.CURRENCY_MISMATCH:
        return (f"Währung weicht ab: Datenbank {fmt_money(internal.amount, internal.currency)} vs. "
                f"Anbieter {fmt_money(provider.amount, provider.currency)}; Beträge sind nicht vergleichbar.")
    if kind is IssueKind.DUPLICATE_IN_DB:
        return (f"Doppelbuchung: Referenz '{internal.reference}' ist mehrfach in der Datenbank; "
                f"{fmt_money(internal.amount, internal.currency)} ist bereits dem Anbietereintrag "
                f"zugeordnet (DB-ID {match.internal.record_id}).")
    if kind is IssueKind.DUPLICATE_IN_PROVIDER:
        return (f"Doppelte Abrechnung: Referenz '{provider.reference}' kommt mehrfach in der Abrechnung vor; "
                f"{fmt_money(provider.amount, provider.currency)} ist bereits der DB-ID "
                f"{match.internal.record_id} zugeordnet.")
    return (f"Zuordnung über unscharfe Suche: Referenz '{internal.reference}' (DB) ↔ "
            f"'{provider.reference}' (Anbieter), Konfidenz {match.confidence:.0%}.")


def _action(kind, internal, provider) -> str:
    if kind is IssueKind.MISSING_IN_PROVIDER:
        if internal.status.settles:
            return "Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren."
        return "Buchung ist nicht abgeschlossen: nächste Abrechnung abwarten und erneut abgleichen."
    if kind is IssueKind.MISSING_IN_DB:
        if provider.status.settles:
            return "Geldeingang dem passenden Vorgang zuordnen und nachbuchen."
        return "Beobachten: Anbietereintrag ist nicht abgeschlossen und hat noch keine finanzielle Wirkung."
    if kind is IssueKind.AMOUNT_MISMATCH:
        return "Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren."
    if kind is IssueKind.STATUS_MISMATCH:
        if provider.status.settles and not internal.status.settles:
            return "Status in der Datenbank aktualisieren (Zahlung ist beim Anbieter abgeschlossen)."
        if internal.status.settles and not provider.status.settles:
            return "Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen."
        return "Status mit dem Anbieter klären; derzeit keine finanzielle Wirkung."
    if kind is IssueKind.CURRENCY_MISMATCH:
        return "Währung der Buchung gegen den Beleg prüfen und Fehlbuchung korrigieren."
    if kind is IssueKind.DUPLICATE_IN_DB:
        return "Doppelbuchung prüfen und die überzählige Buchung stornieren."
    if kind is IssueKind.DUPLICATE_IN_PROVIDER:
        return "Doppelte Abrechnung beim Anbieter reklamieren (mögliche Doppelbelastung)."
    return "Zuordnung bestätigen und die Referenz in der Datenbank korrigieren."
