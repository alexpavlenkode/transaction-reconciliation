"""Orchestrierung: Import -> Matching -> Abweichungen -> Kennzahlen."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from .config import ReconcileConfig
from .discrepancies import find_discrepancies
from .importers import (ImportIssue, ImportResult, InternalDbImporter, ProviderACsvImporter,
                        ProviderBJsonImporter)
from .matching import MatchResult, match_transactions
from .models import Discrepancy, Match, Transaction
from .summary import Summary, summarize


@dataclass
class ReconciliationResult:
    config: ReconcileConfig
    sources: list[ImportResult]
    internal: list[Transaction]
    provider: list[Transaction]
    matching: MatchResult
    discrepancies: list[Discrepancy]
    summary: Summary

    @property
    def import_issues(self) -> list[ImportIssue]:
        return [issue for source in self.sources for issue in source.issues]

    @property
    def incomplete_reasons(self) -> list[str]:
        """Gründe, warum das Ergebnis unvollständig ist: Zeilen, die nicht abgeglichen werden konnten."""
        reasons = []
        for source in self.sources:
            skipped = len(source.errors)
            if skipped:
                keyless = sum(1 for issue in source.errors if not issue.key)
                reasons.append(f"{source.source}: {skipped} Zeile(n) übersprungen"
                               + (f", davon {keyless} ohne lesbare Referenz" if keyless else ""))
        return reasons

    @property
    def incomplete(self) -> bool:
        return bool(self.incomplete_reasons)

    @property
    def flagged_matches(self) -> dict[tuple[str, str], Discrepancy]:
        """Zugeordnete Paare, die eine Abweichung haben (Schlüssel: DB-ID, Anbieter-ID)."""
        return {(d.internal.record_id, d.provider.record_id): d
                for d in self.discrepancies if d.internal and d.provider}

    def sorted_matches(self) -> list[Match]:
        return sorted(self.matching.matches, key=lambda m: (m.internal.timestamp, m.internal.record_id))


def _check_snapshot(source: ImportResult, config: ReconcileConfig) -> ImportResult:
    """Datensätze nach dem Stichtag zeigen, dass die Datei nicht zum Stichtag passt."""
    if config.as_of is None:
        return source
    late = sum(1 for tx in source.transactions if tx.timestamp > config.as_of)
    if not late:
        return source
    issue = ImportIssue(source.source, "Stichtag", "warning",
                        f"{late} Datensatz/Datensätze mit Zeitstempel nach dem Stichtag {config.as_of:%d.%m.%Y %H:%M} "
                        f"UTC: die Eingabedatei passt nicht zum Stichtag.")
    return replace(source, issues=[*source.issues, issue])


def reconcile(internal: ImportResult, providers: Sequence[ImportResult],
              config: ReconcileConfig | None = None) -> ReconciliationResult:
    """Gleicht die interne Quelle mit beliebig vielen Anbieterquellen ab."""
    config = config or ReconcileConfig()
    sources = [_check_snapshot(source, config) for source in (internal, *providers)]
    internal, providers = sources[0], sources[1:]
    provider_txs = [tx for source in providers for tx in source.transactions]
    all_issues = [issue for source in sources for issue in source.issues]

    matching = match_transactions(internal.transactions, provider_txs, config)
    discrepancies = find_discrepancies(matching, config, all_issues)
    summary = summarize(internal.transactions, provider_txs, matching, discrepancies)
    return ReconciliationResult(config, sources, internal.transactions, provider_txs,
                                matching, discrepancies, summary)


def reconcile_files(db: str | Path, provider_a: str | Path, provider_b: str | Path,
                    config: ReconcileConfig | None = None, *, allow_real_amount: bool = False,
                    csv_timezone: str = "UTC") -> ReconciliationResult:
    """Komfortfunktion für die drei Standardquellen (wirft ``SourceError`` bei unlesbaren Quellen)."""
    return reconcile(
        InternalDbImporter(allow_real_amount=allow_real_amount).read(db),
        [ProviderACsvImporter(csv_timezone=csv_timezone).read(provider_a), ProviderBJsonImporter().read(provider_b)],
        config,
    )
