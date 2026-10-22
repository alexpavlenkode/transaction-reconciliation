"""Konfigurierbare Parameter des Abgleichs (alle mit nachvollziehbaren Standardwerten)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

# Nur zur Priorisierung (nicht zur Buchung!): grobe, bewusst statische Umrechnungskurse nach EUR.
# Damit sind 15.800 JPY und 15.800 EUR nicht gleich "dringend". Produktiv: Tageskurse einspeisen.
DEFAULT_FX_TO_EUR: dict[str, Decimal] = {
    "EUR": Decimal("1"),
    "USD": Decimal("0.92"),
    "CHF": Decimal("1.04"),
    "GBP": Decimal("1.17"),
    "JPY": Decimal("0.0061"),
}


@dataclass(frozen=True)
class ReconcileConfig:
    # --- Betragsvergleich ---------------------------------------------------
    amount_tolerance: Decimal = Decimal("0.00")
    """Erlaubte absolute Betragsdifferenz (z. B. 0.01 für Rundungsdifferenzen)."""

    # --- Unscharfe Zuordnung (Fuzzy Matching) ---------------------------------
    fuzzy_enabled: bool = True
    fuzzy_time_window: timedelta = timedelta(days=3)
    fuzzy_min_ref_similarity: float = 0.80
    """Mindest-Ähnlichkeit der normalisierten Referenzen (difflib-Ratio)."""
    fuzzy_min_ref_similarity_if_amount_differs: float = 0.92
    """Weicht auch der Betrag ab, muss die Referenz fast identisch sein: zwei schwache Indizien
    zusammen sind kein Beweis (bei 100.000 Datensätzen erzeugten sie sonst vereinzelt Fehltreffer)."""
    fuzzy_min_score: float = 0.80
    """Mindest-Gesamtscore = 0.6·Referenz + 0.3·Betrag + 0.1·Zeitnähe."""

    # --- Priorisierung (in EUR-Äquivalent der absoluten Auswirkung) ------------------
    high_threshold: Decimal = Decimal("500")
    medium_threshold: Decimal = Decimal("50")
    fx_to_eur: dict[str, Decimal] = field(default_factory=lambda: dict(DEFAULT_FX_TO_EUR))

    # --- Bericht ------------------------------------------------------------------
    max_matched_rows: int = 100
    """Maximale Zahl zugeordneter Zeilen im Markdown-Bericht (JSON/CSV enthalten immer alle)."""
