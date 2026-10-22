"""Zentrale Datenmodelle des Abgleichs.

Alle Quellen werden auf :class:`Transaction` normalisiert; alles Weitere
(Matching, Abweichungen, Berichte) arbeitet nur noch mit diesen Typen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .normalize import normalize_reference


class Status(str, Enum):
    """Vereinheitlichter Transaktionsstatus (Quellwerte werden im Importer abgebildet)."""

    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    UNKNOWN = "UNKNOWN"

    @property
    def settles(self) -> bool:
        """Nur abgeschlossene Zahlungen bewegen tatsächlich Geld zu unseren Gunsten."""
        return self is Status.COMPLETED


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def rank(self) -> int:
        return {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[self.value]


class IssueKind(str, Enum):
    """Arten von Abweichungen. Die Reihenfolge entspricht der Schwere (für die Hauptkategorie)."""

    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    MISSING_IN_PROVIDER = "MISSING_IN_PROVIDER"
    MISSING_IN_DB = "MISSING_IN_DB"
    DUPLICATE_IN_DB = "DUPLICATE_IN_DB"
    DUPLICATE_IN_PROVIDER = "DUPLICATE_IN_PROVIDER"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"


@dataclass(frozen=True)
class Transaction:
    """Eine normalisierte Transaktion aus einer beliebigen Quelle."""

    source: str                  # "internal" | "provider_a" | "provider_b"
    provider: str                # "A" | "B" – welcher Anbieter die Zahlung abwickelt
    record_id: str               # Primärschlüssel in der Quelle (DB-ID bzw. Anbieter-ID)
    reference: str | None        # Roh-Referenz auf die Gegenseite (None = nicht vorhanden)
    amount: Decimal              # immer Decimal, nie float; auf Währungsexponent gerundet
    currency: str                # ISO-4217, Großbuchstaben
    status: Status
    timestamp: datetime          # immer timezone-aware in UTC
    raw_status: str = ""         # Originalwert aus der Quelle (für den Bericht)
    note: str = ""               # z. B. Bestellnummer
    key: str = field(init=False, repr=False, compare=False, default="")

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", normalize_reference(self.reference))


@dataclass(frozen=True)
class Match:
    """Ein zugeordnetes Paar (interne Buchung <-> Anbietereintrag)."""

    internal: Transaction
    provider: Transaction
    method: str                  # "exact" | "fuzzy"
    confidence: float = 1.0


@dataclass
class Discrepancy:
    """Ein auffälliger Datensatz bzw. ein auffälliges Paar mit Priorität und finanzieller Auswirkung."""

    kinds: tuple[IssueKind, ...]
    internal: Transaction | None
    provider: Transaction | None
    impact: dict[str, Decimal]   # Währung -> (Anbieter-Verbuchung − DB-Verbuchung)
    priority: Priority
    description: str
    action: str
    match: Match | None = None

    @property
    def primary_kind(self) -> IssueKind:
        return self.kinds[0]

    @property
    def provider_code(self) -> str:
        tx = self.internal or self.provider
        return tx.provider if tx else "?"
