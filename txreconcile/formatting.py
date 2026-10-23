"""Darstellung von Beträgen und Begriffen im (deutschsprachigen) Bericht."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .models import Certainty, IssueKind, Priority, Status
from .normalize import currency_exponent

STATUS_LABELS = {
    Status.COMPLETED: "abgeschlossen",
    Status.PENDING: "ausstehend",
    Status.FAILED: "fehlgeschlagen",
    Status.REFUNDED: "erstattet",
    Status.UNKNOWN: "unbekannt",
}

PRIORITY_LABELS = {Priority.HIGH: "Hoch", Priority.MEDIUM: "Mittel", Priority.LOW: "Niedrig"}
PRIORITY_ICONS = {Priority.HIGH: "🔴", Priority.MEDIUM: "🟠", Priority.LOW: "🟡"}

KIND_LABELS = {
    IssueKind.CURRENCY_MISMATCH: "Währungsabweichung",
    IssueKind.SOURCE_ROW_UNREADABLE: "Nicht prüfbar (Quellzeile unlesbar)",
    IssueKind.MISSING_IN_PROVIDER: "Fehlt in Abrechnung",
    IssueKind.MISSING_IN_DB: "Fehlt in Datenbank",
    IssueKind.NOT_YET_DUE: "Noch nicht fällig",
    IssueKind.DUPLICATE_IN_DB: "Mehrfach in Datenbank",
    IssueKind.DUPLICATE_IN_PROVIDER: "Mehrfach in Abrechnung",
    IssueKind.ID_COLLISION: "Mögliche ID-Kollision",
    IssueKind.STATUS_MISMATCH: "Statusabweichung",
    IssueKind.AMOUNT_MISMATCH: "Betragsabweichung",
    IssueKind.REFERENCE_MISMATCH: "Unscharfe Zuordnung",
}


def fmt_number(value: Decimal, currency: str = "EUR", signed: bool = False) -> str:
    """Deutsches Zahlenformat: ``1.234,56``; JPY ohne Nachkommastellen."""
    digits = currency_exponent(currency)
    text = f"{value:{'+' if signed else ''},.{digits}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def fmt_money(value: Decimal, currency: str, signed: bool = False) -> str:
    return f"{fmt_number(value, currency, signed)} {currency}"


def fmt_impact(impact: dict[str, Decimal], signed: bool = True) -> str:
    """``{'EUR': -45}`` -> ``-45,00 EUR``; mehrere Währungen mit ``/`` getrennt; leer -> ``±0``."""
    parts = [fmt_money(v, c, signed) for c, v in sorted(impact.items()) if v != 0]
    return " / ".join(parts) if parts else "±0"


def fmt_amounts(amounts: dict[str, Decimal]) -> str:
    """Unsignierte Beträge je Währung: ``200,00 EUR / 200,00 USD``."""
    return " / ".join(fmt_money(v, c) for c, v in sorted(amounts.items())) if amounts else "—"


def fmt_time(moment: datetime | None) -> str:
    return moment.strftime("%d.%m.%Y %H:%M") if moment else "—"


CERTAINTY_LABELS = {
    Certainty.CALCULATED: "berechnet",
    Certainty.PRELIMINARY: "vorläufig",
    Certainty.UNDEFINED: "nicht bestimmbar",
}


def fmt_effect(item) -> str:
    """Auswirkung eines Befunds für Tabellen: Zahl, ``±0`` oder ``nicht bestimmbar (betroffen: …)``."""
    if item.certainty is Certainty.UNDEFINED:
        return f"nicht bestimmbar (betroffen: {fmt_amounts(item.affected)})"
    text = fmt_impact(item.impact)
    return f"{text} (vorläufig)" if item.certainty is Certainty.PRELIMINARY else text
