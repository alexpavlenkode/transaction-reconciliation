"""Erkennung und Bewertung von Abweichungen.

Finanzielle Auswirkung (zentrale Definition)
--------------------------------------------
Jede Seite hat einen *verbuchten Betrag* (Modell: die Quellen sind Zustands-Schnappschüsse):

    COMPLETED               -> Betrag
    PENDING / FAILED        -> 0
    REFUNDED                -> 0   (vollständige Erstattung im Schnappschuss-Modell)
    UNKNOWN                 -> nicht bestimmt (NICHT 0!)

    Auswirkung = verbuchter Betrag (Anbieter) − verbuchter Betrag (Datenbank)        je Währung

* negativ: die Datenbank erwartet mehr Geld, als der Anbieter abrechnet (Fehlbetrag / Forderung offen)
* positiv: der Anbieter rechnet mehr ab, als die Datenbank kennt (nicht gebuchter Geldeingang)

Dieselbe Formel gilt für alle Befunde mit bestimmbarer Auswirkung; bei Datensätzen mit *mehreren* Befunden
wird sie genau einmal gezählt. Währungen werden nie verrechnet und nie umgerechnet.

Wann die Auswirkung NICHT bestimmbar ist (``Certainty.UNDEFINED``) – dann gibt es keine Summe, nur den
*betroffenen Betrag* (``affected``), und die Schwere richtet sich nach diesem Betrag:

* ein Status ist ``UNKNOWN`` (ein erfundener Nullwert wäre eine erfundene Abweichung)
* Währungen weichen ab (kein Kurs, keine Subtraktion)
* Duplikate / ID-Kollisionen (doppelte Zeile oder doppelte Zahlung – nicht entscheidbar)
* die Gegenseite hat zu dieser Referenz eine unlesbare Zeile (``SOURCE_ROW_UNREADABLE``)
* die Buchung ist noch innerhalb der Abrechnungsfrist (``NOT_YET_DUE``)

``Certainty.PRELIMINARY``: berechnet, aber die Quelle enthält Zeilen ohne lesbare Referenz – jede
"fehlt"-Aussage zu dieser Seite kann dadurch erklärt werden.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .config import ReconcileConfig
from .formatting import STATUS_LABELS, fmt_money, fmt_time
from .importers.base import ImportIssue
from .matching import MatchResult
from .models import Certainty, Discrepancy, IssueKind, Match, Priority, Status, Transaction

_KIND_ORDER = {kind: n for n, kind in enumerate(IssueKind)}

UNDEFINED_KINDS = frozenset({
    IssueKind.CURRENCY_MISMATCH, IssueKind.SOURCE_ROW_UNREADABLE, IssueKind.NOT_YET_DUE,
    IssueKind.DUPLICATE_IN_DB, IssueKind.DUPLICATE_IN_PROVIDER, IssueKind.ID_COLLISION,
})


# ---------------------------------------------------------------------------
# Beträge, Auswirkung, Schwere
# ---------------------------------------------------------------------------

def booked_amount(tx: Transaction | None) -> Decimal:
    """Verbuchter Betrag: nur abgeschlossene Zahlungen zählen (UNKNOWN wird vom Aufrufer vorab ausgeschlossen)."""
    return tx.amount if tx is not None and tx.status.settles else Decimal(0)


def effect_determinable(*transactions: Transaction | None) -> bool:
    return all(tx is None or tx.status is not Status.UNKNOWN for tx in transactions)


def net_impact(internal: Transaction | None, provider: Transaction | None) -> dict[str, Decimal]:
    impact: dict[str, Decimal] = defaultdict(Decimal)
    if provider is not None:
        impact[provider.currency] += booked_amount(provider)
    if internal is not None:
        impact[internal.currency] -= booked_amount(internal)
    return {currency: value for currency, value in impact.items() if value != 0}


def affected_amount(internal: Transaction | None, provider: Transaction | None) -> dict[str, Decimal]:
    """Betroffener Betrag je Währung: der größere Betrag der beteiligten Datensätze. Kein Effekt, keine Summe."""
    affected: dict[str, Decimal] = {}
    for tx in (internal, provider):
        if tx is not None:
            affected[tx.currency] = max(affected.get(tx.currency, Decimal(0)), abs(tx.amount))
    return affected


def level(amounts: dict[str, Decimal], config: ReconcileConfig) -> Priority:
    """Schwere nach den Schwellen der jeweiligen Währung; die höchste Stufe aller Währungen gilt."""
    best = Priority.LOW
    for currency, value in amounts.items():
        high, medium = config.thresholds(currency)
        size = abs(value)
        current = Priority.HIGH if size >= high else Priority.MEDIUM if size >= medium else Priority.LOW
        if current.rank < best.rank:
            best = current
    return best


def magnitude(amounts: dict[str, Decimal], config: ReconcileConfig) -> Decimal:
    """Sortiermaß innerhalb einer Stufe: Betrag relativ zur 'hoch'-Schwelle seiner Währung (kein Kurs nötig)."""
    return max((abs(v) / config.thresholds(c)[0] for c, v in amounts.items()), default=Decimal(0))


def is_due(tx: Transaction, config: ReconcileConfig) -> bool:
    """Überfällig genau dann, wenn ``as_of > Buchungszeit + Frist``. Ohne Stichtag gilt alles als fällig."""
    return config.as_of is None or config.as_of > tx.timestamp + config.settlement_lag


def prioritize(kinds: tuple[IssueKind, ...], certainty: Certainty, impact: dict[str, Decimal],
               affected: dict[str, Decimal], config: ReconcileConfig, overdue: bool = False) -> Priority:
    if IssueKind.CURRENCY_MISMATCH in kinds:
        return Priority.HIGH                 # Beträge sind nicht vergleichbar -> immer manuell klären
    if IssueKind.NOT_YET_DUE in kinds:
        return Priority.LOW                  # innerhalb der Frist: nur beobachten
    priority = level(impact if certainty is not Certainty.UNDEFINED else affected, config)
    if overdue and priority is Priority.LOW:
        priority = Priority.MEDIUM           # erwartete Abrechnung fehlt nach Fristablauf
    return priority


# ---------------------------------------------------------------------------
# Kontext aus den Importmeldungen
# ---------------------------------------------------------------------------

class _IssueContext:
    """Verknüpft Importfehler mit Befunden: keine falsche "fehlt"-Aussage, wo eine Zeile nur unlesbar war."""

    def __init__(self, issues: list[ImportIssue]) -> None:
        self.provider_rows: dict[tuple[str | None, str], ImportIssue] = {}
        self.internal_rows: dict[tuple[str | None, str], ImportIssue] = {}
        self.keyless_sources: set[str] = set()
        for issue in issues:
            if issue.severity != "error":
                continue
            if not issue.key:
                self.keyless_sources.add(issue.source)
            elif issue.source == "internal":
                self.internal_rows.setdefault((issue.provider, issue.key), issue)
            else:
                self.provider_rows.setdefault((issue.provider, issue.key), issue)

    def unreadable_provider_row(self, tx: Transaction) -> ImportIssue | None:
        return self.provider_rows.get((tx.provider, tx.key))

    def unreadable_internal_row(self, tx: Transaction) -> ImportIssue | None:
        return self.internal_rows.get((tx.provider, tx.key)) or self.internal_rows.get((None, tx.key))


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def find_discrepancies(matching: MatchResult, config: ReconcileConfig,
                       import_issues: list[ImportIssue] | None = None) -> list[Discrepancy]:
    context = _IssueContext(import_issues or [])
    found: list[Discrepancy] = []

    for match in matching.matches:
        kinds = _compare(match, config)
        if kinds:
            found.append(_build(kinds, match.internal, match.provider, config, match=match))

    for tx in matching.unmatched_internal:
        issue = context.unreadable_provider_row(tx)
        if issue:
            found.append(_build((IssueKind.SOURCE_ROW_UNREADABLE,), tx, None, config, issue=issue))
        elif not is_due(tx, config):
            found.append(_build((IssueKind.NOT_YET_DUE,), tx, None, config))
        else:
            preliminary = f"provider_{tx.provider.lower()}" in context.keyless_sources
            found.append(_build((IssueKind.MISSING_IN_PROVIDER,), tx, None, config,
                                preliminary=preliminary, overdue=True))
    for tx in matching.unmatched_provider:
        issue = context.unreadable_internal_row(tx)
        if issue:
            found.append(_build((IssueKind.SOURCE_ROW_UNREADABLE,), None, tx, config, issue=issue))
        else:
            found.append(_build((IssueKind.MISSING_IN_DB,), None, tx, config,
                                preliminary="internal" in context.keyless_sources))
    for tx, original in matching.duplicate_internal:
        kinds = (IssueKind.DUPLICATE_IN_DB,) + _collision(tx, original.internal)
        found.append(_build(kinds, tx, None, config, match=original))
    for tx, original in matching.duplicate_provider:
        kinds = (IssueKind.DUPLICATE_IN_PROVIDER,) + _collision(tx, original.provider)
        found.append(_build(kinds, None, tx, config, match=original))

    found.sort(key=lambda d: (
        d.priority.rank,
        -magnitude(d.impact if d.effect_defined else d.affected, config),
        _KIND_ORDER[d.primary_kind], (d.internal or d.provider).timestamp,
        d.provider_code, (d.internal or d.provider).record_id))
    return found


def _collision(extra: Transaction, original: Transaction) -> tuple[IssueKind, ...]:
    """Unterscheiden sich die Rohreferenzen, ist es womöglich gar kein Duplikat, sondern eine Kollision
    durch die Normalisierung (z. B. ``ATX-1`` und ``ATX1`` gelten bei A als dieselbe ID)."""
    if (extra.reference or "").strip() != (original.reference or "").strip():
        return (IssueKind.ID_COLLISION,)
    return ()


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


def _build(kinds, internal, provider, config, *, match=None, issue=None, preliminary=False,
           overdue=False) -> Discrepancy:
    kinds = tuple(sorted(kinds, key=_KIND_ORDER.__getitem__))
    if UNDEFINED_KINDS & set(kinds) or not effect_determinable(internal, provider):
        certainty = Certainty.UNDEFINED
    elif preliminary:
        certainty = Certainty.PRELIMINARY
    else:
        certainty = Certainty.CALCULATED
    impact = net_impact(internal, provider) if certainty is not Certainty.UNDEFINED else {}
    affected = affected_amount(internal, provider)
    description = " ".join(_describe(kind, internal, provider, match, issue, config) for kind in kinds)
    if certainty is Certainty.UNDEFINED and not (UNDEFINED_KINDS & set(kinds)):
        description += " Der Status ist unbekannt: die Auswirkung ist nicht bestimmbar, nur der betroffene Betrag wird ausgewiesen."
    if preliminary:
        description += " Vorläufig: die Quelle enthält Zeilen ohne lesbare Referenz, die diesen Befund erklären könnten."
    return Discrepancy(
        kinds=kinds, internal=internal, provider=provider, impact=impact, affected=affected, certainty=certainty,
        priority=prioritize(kinds, certainty, impact, affected, config, overdue),
        description=description, action=" ".join(_action(kind, internal, provider) for kind in kinds), match=match,
    )


# ---------------------------------------------------------------------------
# Texte (deutsch, handlungsorientiert)
# ---------------------------------------------------------------------------

def _status_text(tx: Transaction) -> str:
    label = STATUS_LABELS[tx.status]
    return f"{label} ('{tx.raw_status}')" if tx.status is Status.UNKNOWN else label


def _describe(kind, internal, provider, match, issue, config) -> str:
    if kind is IssueKind.MISSING_IN_PROVIDER:
        text = (f"Nur in der Datenbank: {fmt_money(internal.amount, internal.currency)} "
                f"({_status_text(internal)}) vom {fmt_time(internal.timestamp)}; "
                f"Abrechnung von Anbieter {internal.provider} enthält keinen Eintrag, obwohl die Frist von "
                f"{config.settlement_lag.days} Tagen abgelaufen ist.")
        if not internal.reference:
            text += " Es ist keine Provider-Referenz hinterlegt."
        return text
    if kind is IssueKind.NOT_YET_DUE:
        due = internal.timestamp + config.settlement_lag
        return (f"Noch nicht fällig: Buchung vom {fmt_time(internal.timestamp)} "
                f"({fmt_money(internal.amount, internal.currency)}, {_status_text(internal)}); "
                f"die Abrechnung wird bis {fmt_time(due)} erwartet (Stichtag {fmt_time(config.as_of)}).")
    if kind is IssueKind.MISSING_IN_DB:
        return (f"Nur in der Abrechnung von Anbieter {provider.provider}: "
                f"{fmt_money(provider.amount, provider.currency)} ({_status_text(provider)}) "
                f"vom {fmt_time(provider.timestamp)}; keine passende Buchung in der Datenbank.")
    if kind is IssueKind.SOURCE_ROW_UNREADABLE:
        tx = internal or provider
        where = (f"die Abrechnung von Anbieter {tx.provider}" if internal is not None else "die Datenbank")
        side = "Nur in der Datenbank" if internal is not None else f"Nur in der Abrechnung von Anbieter {tx.provider}"
        return (f"Nicht prüfbar: {side}: {fmt_money(tx.amount, tx.currency)} ({_status_text(tx)}) "
                f"vom {fmt_time(tx.timestamp)}. Zu dieser Referenz enthält {where} eine unlesbare Zeile "
                f"({issue.location}: {issue.message}). Ob ein Eintrag fehlt, lässt sich erst nach Korrektur "
                f"der Quelle sagen.")
    if kind is IssueKind.AMOUNT_MISMATCH:
        diff = provider.amount - internal.amount
        return (f"Betrag weicht ab: Datenbank {fmt_money(internal.amount, internal.currency)} vs. "
                f"Anbieter {fmt_money(provider.amount, provider.currency)} "
                f"(Differenz {fmt_money(diff, internal.currency, signed=True)}).")
    if kind is IssueKind.STATUS_MISMATCH:
        return f"Status weicht ab: Datenbank {_status_text(internal)} vs. Anbieter {_status_text(provider)}."
    if kind is IssueKind.CURRENCY_MISMATCH:
        return (f"Währung weicht ab: Datenbank {fmt_money(internal.amount, internal.currency)} vs. "
                f"Anbieter {fmt_money(provider.amount, provider.currency)}; die Beträge sind nicht vergleichbar, "
                f"eine Auswirkung wird ohne Kurs nicht berechnet.")
    if kind is IssueKind.DUPLICATE_IN_DB:
        return (f"Mehrfacher Eintrag in der Datenbank: Referenz '{internal.reference}' kommt mehrfach vor "
                f"({fmt_money(internal.amount, internal.currency)}); ein Eintrag ist bereits dem Anbietereintrag "
                f"zugeordnet (DB-ID {match.internal.record_id}). Ob Doppelbuchung oder Doppelzeile, ist aus den "
                f"Daten nicht bestimmbar – betroffener Betrag, keine berechnete Auswirkung.")
    if kind is IssueKind.DUPLICATE_IN_PROVIDER:
        return (f"Mehrfacher Eintrag in der Abrechnung: Referenz '{provider.reference}' kommt mehrfach vor "
                f"({fmt_money(provider.amount, provider.currency)}); ein Eintrag ist bereits der DB-ID "
                f"{match.internal.record_id} zugeordnet. Ob doppelte Zahlung oder doppelte Zeile, ist aus den "
                f"Daten nicht bestimmbar – betroffener Betrag, keine berechnete Auswirkung.")
    if kind is IssueKind.ID_COLLISION:
        extra = internal or provider
        original = match.internal if internal is not None else match.provider
        return (f"Mögliche ID-Kollision: '{extra.reference}' und '{original.reference}' sind nur nach der "
                f"Normalisierung gleich (Regel des Anbieters {extra.provider}); es kann sich um verschiedene "
                f"Transaktionen handeln.")
    return (f"Zuordnung über unscharfe Suche: Referenz '{internal.reference}' (DB) ↔ "
            f"'{provider.reference}' (Anbieter), Konfidenz {match.confidence:.0%}.")


def _action(kind, internal, provider) -> str:
    if kind is IssueKind.MISSING_IN_PROVIDER:
        if internal.status.settles:
            return "Beim Anbieter nachfragen, ob die Zahlung eingegangen ist; ohne Beleg Forderung offen halten bzw. stornieren."
        return "Buchung ist nicht abgeschlossen: beim Anbieter den Stand erfragen, da die Frist abgelaufen ist."
    if kind is IssueKind.NOT_YET_DUE:
        return "Nichts tun: bis zum Fristende abwarten und erneut abgleichen."
    if kind is IssueKind.SOURCE_ROW_UNREADABLE:
        return "Unlesbare Zeile in der Quelle korrigieren oder neu anfordern und den Abgleich wiederholen."
    if kind is IssueKind.MISSING_IN_DB:
        if provider.status.settles:
            return "Geldeingang dem passenden Vorgang zuordnen und nachbuchen."
        return "Beobachten: Anbietereintrag ist nicht abgeschlossen und hat noch keine finanzielle Wirkung."
    if kind is IssueKind.AMOUNT_MISMATCH:
        return "Korrekten Betrag am Beleg klären; Differenz beim Anbieter reklamieren oder Buchung korrigieren."
    if kind is IssueKind.STATUS_MISMATCH:
        if Status.UNKNOWN in (internal.status, provider.status):
            return "Unbekannten Anbieterstatus beim Anbieter erfragen und in die Statuszuordnung aufnehmen."
        if provider.status.settles and not internal.status.settles:
            return "Status in der Datenbank aktualisieren (Zahlung ist beim Anbieter abgeschlossen)."
        if internal.status.settles and not provider.status.settles:
            return "Zahlung ist beim Anbieter nicht abgeschlossen: Forderung wieder öffnen und Leistung/Versand prüfen."
        return "Status mit dem Anbieter klären; derzeit keine finanzielle Wirkung."
    if kind is IssueKind.CURRENCY_MISMATCH:
        return "Währung der Buchung gegen den Beleg prüfen und Fehlbuchung korrigieren."
    if kind is IssueKind.DUPLICATE_IN_DB:
        return "Prüfen, ob eine Doppelbuchung oder nur eine doppelte Zeile vorliegt; Doppelbuchung stornieren."
    if kind is IssueKind.DUPLICATE_IN_PROVIDER:
        return "Beim Anbieter klären, ob doppelt belastet wurde; bei Doppelbelastung reklamieren."
    if kind is IssueKind.ID_COLLISION:
        return "Rohwerte der IDs gegen den Beleg prüfen und ggf. die ID-Regel des Anbieters anpassen."
    return "Zuordnung bestätigen und die Referenz in der Datenbank korrigieren."
