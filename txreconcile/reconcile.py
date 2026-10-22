"""Orchestrierung: Import -> Matching -> Abweichungen -> Kennzahlen."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def import_issues(self) -> list[ImportIssue]:
        return [issue for source in self.sources for issue in source.issues]

    @property
    def flagged_matches(self) -> dict[tuple[str, str], Discrepancy]:
        """Zugeordnete Paare, die eine Abweichung haben (Schlüssel: DB-ID, Anbieter-ID)."""
        return {(d.internal.record_id, d.provider.record_id): d
                for d in self.discrepancies if d.internal and d.provider}

    def sorted_matches(self) -> list[Match]:
        return sorted(self.matching.matches, key=lambda m: (m.internal.timestamp, m.internal.record_id))


def reconcile(internal: ImportResult, providers: Sequence[ImportResult],
              config: ReconcileConfig | None = None) -> ReconciliationResult:
    """Gleicht die interne Quelle mit beliebig vielen Anbieterquellen ab."""
    config = config or ReconcileConfig()
    provider_txs = [tx for source in providers for tx in source.transactions]
    sources = [internal, *providers]
    all_issues = [issue for source in sources for issue in source.issues]

    matching = match_transactions(internal.transactions, provider_txs, config)
    discrepancies = find_discrepancies(matching, config, all_issues)
    summary = summarize(internal.transactions, provider_txs, matching, discrepancies)
    return ReconciliationResult(config, sources, internal.transactions, provider_txs,
                                matching, discrepancies, summary)


def reconcile_files(db: str | Path, provider_a: str | Path, provider_b: str | Path,
                    config: ReconcileConfig | None = None) -> ReconciliationResult:
    """Komfortfunktion für die drei Standardquellen (wirft ``SourceError`` bei unlesbaren Quellen)."""
    return reconcile(
        InternalDbImporter().read(db),
        [ProviderACsvImporter().read(provider_a), ProviderBJsonImporter().read(provider_b)],
        config,
    )
