"""Parser und Normalisierer für Referenzen, Beträge, Währungen und Zeitstempel.

Grundsätze:

* Geld ist immer :class:`~decimal.Decimal` – ``float`` wird nie für Rechnungen verwendet.
* Zeitstempel sind danach immer timezone-aware in UTC.
* Ungültige Eingaben lösen ``ValueError`` aus; die Importer machen daraus eine
  Importmeldung und überspringen nur die betroffene Zeile.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ISO 4217: Währungen mit abweichender Anzahl Nachkommastellen (Standard: 2)
CURRENCY_EXPONENTS = {
    "JPY": 0, "KRW": 0, "CLP": 0, "ISK": 0, "VND": 0, "UGX": 0,
    "KWD": 3, "BHD": 3, "JOD": 3, "OMR": 3, "TND": 3,
}

_NON_ALNUM = re.compile(r"[\W_]+")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_GERMAN_AMOUNT = re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")


def normalize_reference(reference: str | None) -> str:
    """Schlüssel für den Abgleich: ``' atx-123 '`` und ``'ATX123'`` ergeben dasselbe."""
    if not reference:
        return ""
    return _NON_ALNUM.sub("", reference.upper())


def currency_exponent(currency: str) -> int:
    return CURRENCY_EXPONENTS.get(currency, 2)


def quantize_money(value: Decimal, currency: str) -> Decimal:
    """Rundet auf die Nachkommastellen der Währung (kaufmännisch)."""
    return value.quantize(Decimal(1).scaleb(-currency_exponent(currency)), rounding=ROUND_HALF_UP)


def normalize_currency(value: object) -> str:
    text = str(value or "").strip().upper()
    if not _CURRENCY.match(text):
        raise ValueError(f"ungültige Währung: {value!r}")
    return text


def _finite(value: Decimal, original: object) -> Decimal:
    if not value.is_finite():
        raise ValueError(f"ungültiger Betrag: {original!r}")
    return value


def parse_decimal(value: object) -> Decimal:
    """Betrag aus Datenbank/JSON. ``REAL`` wird über seine kürzeste Textform gelesen (19.99, nicht 19.989999…)."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"ungültiger Betrag: {value!r}")
    try:
        return _finite(Decimal(str(value).strip()), value)
    except InvalidOperation:
        raise ValueError(f"ungültiger Betrag: {value!r}") from None


def parse_german_amount(text: str) -> Decimal:
    """``'1.234,56'`` -> ``Decimal('1234.56')``; strikt, damit Fehler nicht still durchrutschen."""
    cleaned = (text or "").strip().replace(" ", "").replace(" ", "")
    if not _GERMAN_AMOUNT.match(cleaned):
        raise ValueError(f"ungültiger Betrag: {text!r}")
    return Decimal(cleaned.replace(".", "").replace(",", "."))


def parse_minor_units(minor: object, currency: str) -> Decimal:
    """Ganzzahliger Betrag in kleinster Einheit (Cent) -> Dezimalbetrag; JPY hat 0, KWD 3 Stellen."""
    if isinstance(minor, bool) or minor is None:
        raise ValueError(f"ungültiger Betrag (minor): {minor!r}")
    if isinstance(minor, float):
        if not minor.is_integer():
            raise ValueError(f"ungültiger Betrag (minor): {minor!r}")
        minor = int(minor)
    try:
        whole = int(str(minor).strip())
    except ValueError:
        raise ValueError(f"ungültiger Betrag (minor): {minor!r}") from None
    return Decimal(whole).scaleb(-currency_exponent(currency))


def to_utc(moment: datetime) -> datetime:
    """Naive Zeitstempel gelten als UTC, aware werden nach UTC umgerechnet."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def parse_iso_timestamp(text: object) -> datetime:
    value = str(text or "").strip()
    if not value:
        raise ValueError("leerer Zeitstempel")
    if value[-1] in "zZ":                       # fromisoformat kennt "Z" erst ab Python 3.11
        value = value[:-1] + "+00:00"
    try:
        return to_utc(datetime.fromisoformat(value))
    except ValueError:
        raise ValueError(f"ungültiger Zeitstempel: {text!r}") from None


def parse_german_timestamp(text: str) -> datetime:
    """``'03.03.2025 10:15:22'`` (UTC) – Sekunden optional."""
    value = (text or "").strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"ungültiger Zeitstempel: {text!r}")
