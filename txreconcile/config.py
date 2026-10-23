"""Konfigurierbare Parameter des Abgleichs (alle mit nachvollziehbaren Standardwerten)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class ReconcileConfig:
    # --- Stichtag und Fristen -------------------------------------------------
    as_of: datetime | None = None
    """Stichtag der Auswertung (aware, UTC). Der Abgleich hängt nie von der Systemuhr ab. Die Eingabedateien
    müssen den Stand zu diesem Stichtag zeigen. ``None`` = keine Fälligkeitsprüfung (alles gilt als fällig)."""
    settlement_lag: timedelta = timedelta(days=3)
    """Zulässige Verzögerung bis eine Buchung in der Abrechnung erscheinen muss. Überfällig ist eine
    Buchung genau dann, wenn ``as_of > Buchungszeit + settlement_lag`` (strikt größer)."""

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

    # --- Schwere: Schwellen JE WÄHRUNG – bewusst ohne Umrechnungskurse ----------------
    high_threshold: Decimal = Decimal("500")
    medium_threshold: Decimal = Decimal("50")
    """Standardschwellen für alle Währungen ohne eigenen Eintrag in ``currency_thresholds``."""
    currency_thresholds: dict[str, tuple[Decimal, Decimal]] = field(
        default_factory=lambda: {"JPY": (Decimal("75000"), Decimal("7500"))})
    """``{Währung: (hoch, mittel)}`` – eigene Schwellen, wo die Größenordnung abweicht (z. B. JPY)."""

    # --- Bericht ------------------------------------------------------------------
    max_matched_rows: int = 100
    """Maximale Zahl zugeordneter Zeilen im Markdown-Bericht (JSON/CSV enthalten immer alle)."""

    def thresholds(self, currency: str) -> tuple[Decimal, Decimal]:
        """(hoch, mittel) für eine Währung."""
        return self.currency_thresholds.get(currency, (self.high_threshold, self.medium_threshold))
