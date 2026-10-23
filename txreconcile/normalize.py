"""Parser und Normalisierer für Referenzen, Beträge, Währungen und Zeitstempel.

Grundsätze:

* Geld ist immer :class:`~decimal.Decimal` – ``float`` wird nie für Rechnungen verwendet.
* Beträge kommen als **ganzzahlige Minor Units** (Cent) oder als streng geparster Text; es wird nichts
  "erraten". Nur der ausdrückliche Altbestands-Modus für ``REAL`` rundet (siehe ``parse_legacy_real``).
* Zeitstempel sind danach immer timezone-aware in UTC. Zeiten ohne Offset brauchen eine definierte Zone;
  mehrdeutige oder nicht existierende Ortszeiten (Zeitumstellung) werden abgelehnt statt geraten.
* Ungültige Eingaben lösen ``ValueError`` aus; die Importer machen daraus eine
  Importmeldung und überspringen nur die betroffene Zeile.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ISO 4217: Währungen mit abweichender Anzahl Nachkommastellen (Standard: 2)
CURRENCY_EXPONENTS = {
    "JPY": 0, "KRW": 0, "CLP": 0, "ISK": 0, "VND": 0, "UGX": 0,
    "KWD": 3, "BHD": 3, "JOD": 3, "OMR": 3, "TND": 3,
}

_SEPARATORS = re.compile(r"[\W_]+")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_GERMAN_AMOUNT = re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")


# ---------------------------------------------------------------------------
# Referenzen: Normalisierung nach den Regeln des jeweiligen Anbieters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdRule:
    """Wie Transaktions-IDs eines Anbieters verglichen werden.

    Die Regel gehört zum Anbieter, nicht zum Programm: Ob ``abc`` und ``ABC`` dieselbe Transaktion
    sind, bestimmt das Datenformat des Anbieters. Der Rohwert bleibt immer erhalten.
    """

    case_sensitive: bool = False
    ignore_separators: bool = True     # Bindestriche, Unterstriche, Leerzeichen im Inneren

DEFAULT_ID_RULE = IdRule()

# Vertrag der Testdaten: A-IDs sind großschreibungs-unabhängig und trennzeichen-tolerant,
# B-IDs sind exakte, kleingeschriebene Tokens.
ID_RULES: dict[str, IdRule] = {
    "A": IdRule(case_sensitive=False, ignore_separators=True),
    "B": IdRule(case_sensitive=True, ignore_separators=False),
}


def normalize_reference(reference: str | None, rule: IdRule = DEFAULT_ID_RULE) -> str:
    """Schlüssel für den Abgleich. Standardregel: ``' atx-123 '`` und ``'ATX123'`` ergeben dasselbe."""
    if not reference:
        return ""
    text = reference.strip()
    if not rule.case_sensitive:
        text = text.upper()
    if rule.ignore_separators:
        text = _SEPARATORS.sub("", text)
    return text


# ---------------------------------------------------------------------------
# Beträge und Währungen
# ---------------------------------------------------------------------------

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


def parse_legacy_real(value: object, currency: str) -> Decimal:
    """NUR für den Altbestands-Modus: ``REAL`` ist eine Näherung (IEEE-754) und kann die ursprüngliche
    Dezimalzahl nicht beweisen. Hier wird über die kürzeste Textdarstellung gelesen und kaufmännisch
    auf die Währungsgenauigkeit gerundet – korrekt, solange der Originalbetrag ≤ 15 signifikante
    Stellen hatte, aber eben eine Annahme."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"ungültiger Betrag: {value!r}")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"ungültiger Betrag: {value!r}") from None
    if not number.is_finite():
        raise ValueError(f"ungültiger Betrag: {value!r}")
    return quantize_money(number, currency)


def parse_german_amount(text: str) -> Decimal:
    """``'1.234,56'`` -> ``Decimal('1234.56')``; strikt, damit Fehler nicht still durchrutschen."""
    cleaned = (text or "").strip().replace(" ", "").replace(" ", "")
    if not _GERMAN_AMOUNT.match(cleaned):
        raise ValueError(f"ungültiger Betrag: {text!r}")
    return Decimal(cleaned.replace(".", "").replace(",", "."))


def parse_minor_units(minor: object, currency: str) -> Decimal:
    """Ganzzahliger Betrag in kleinster Einheit (Cent) -> Dezimalbetrag; JPY hat 0, KWD 3 Stellen.

    Streng: nur echte ``int``-Werte. Fließkommazahlen (auch ``1234.0``), Texte und Wahrheitswerte
    werden abgelehnt – ein Betrag, der nicht exakt ganzzahlig geliefert wird, ist ein Datenfehler.
    """
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise ValueError(f"Betrag (minor units) muss eine ganze Zahl sein: {minor!r}")
    return Decimal(minor).scaleb(-currency_exponent(currency))


# ---------------------------------------------------------------------------
# Zeit
# ---------------------------------------------------------------------------

def get_timezone(name: str) -> tzinfo:
    """``'UTC'`` oder ein IANA-Name (``'Europe/Berlin'``). Unter Windows braucht das das Paket ``tzdata``."""
    if name.strip().upper() in ("UTC", "Z"):
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        return ZoneInfo(name)
    except (ImportError, ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Zeitzone {name!r} nicht verfügbar (unter Windows: 'pip install tzdata')") from None


def to_utc(moment: datetime) -> datetime:
    """Naive Zeitstempel gelten als UTC, aware werden nach UTC umgerechnet."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def localize(naive: datetime, zone: tzinfo) -> datetime:
    """Ortszeit ohne Offset -> UTC. Bei der Zeitumstellung gibt es Uhrzeiten, die zweimal (Herbst) oder
    gar nicht (Frühling) existieren; welche gemeint ist, lässt sich nicht erraten -> Fehler."""
    if zone is timezone.utc:
        return naive.replace(tzinfo=timezone.utc)
    earlier = naive.replace(tzinfo=zone, fold=0)
    later = naive.replace(tzinfo=zone, fold=1)
    if earlier.utcoffset() != later.utcoffset():
        raise ValueError(f"Ortszeit {naive:%d.%m.%Y %H:%M:%S} ist wegen der Zeitumstellung mehrdeutig "
                         f"oder existiert nicht")
    return earlier.astimezone(timezone.utc)


def parse_iso_timestamp(text: object) -> datetime:
    """ISO-8601. Ohne Offset (z. B. SQLite ``YYYY-MM-DD HH:MM:SS``) gilt UTC – so ist der Datenvertrag."""
    value = str(text or "").strip()
    if not value:
        raise ValueError("leerer Zeitstempel")
    if value[-1] in "zZ":                       # fromisoformat kennt "Z" erst ab Python 3.11
        value = value[:-1] + "+00:00"
    try:
        return to_utc(datetime.fromisoformat(value))
    except ValueError:
        raise ValueError(f"ungültiger Zeitstempel: {text!r}") from None


def parse_german_timestamp(text: str, zone: tzinfo = timezone.utc) -> datetime:
    """``'03.03.2025 10:15:22'`` in der angegebenen Zone (Standard UTC) – Sekunden optional."""
    value = (text or "").strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            naive = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return localize(naive, zone)
    raise ValueError(f"ungültiger Zeitstempel: {text!r}")
