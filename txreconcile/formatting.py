"""Darstellung von Beträgen und Begriffen im (deutschsprachigen) Bericht."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .models import IssueKind, Priority, Status
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
    IssueKind.MISSING_IN_PROVIDER: "Fehlt in Abrechnung",
    IssueKind.MISSING_IN_DB: "Fehlt in Datenbank",
    IssueKind.DUPLICATE_IN_DB: "Duplikat in Datenbank",
    IssueKind.DUPLICATE_IN_PROVIDER: "Duplikat in Abrechnung",
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


def fmt_time(moment: datetime) -> str:
    return moment.strftime("%d.%m.%Y %H:%M")
