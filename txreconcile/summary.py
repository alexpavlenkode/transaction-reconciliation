"""Kennzahlen für den Bericht (reine Auswertung, keine Abgleichslogik).

Geldsummen enthalten nur Befunde mit bestimmbarer Auswirkung (``CALCULATED`` und ``PRELIMINARY``).
Befunde mit nicht bestimmbarer Auswirkung erscheinen getrennt: Anzahl und *betroffener Betrag* je Währung –
sie werden nie in die Auswirkungssumme gemischt.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .matching import MatchResult
from .models import Certainty, Discrepancy, IssueKind, Priority, Transaction


def _add(target: dict[str, Decimal], amounts: dict[str, Decimal], absolute: bool = False) -> None:
    for currency, value in amounts.items():
        target[currency] += abs(value) if absolute else value


def _money_dict() -> dict[str, Decimal]:
    return defaultdict(Decimal)


@dataclass
class KindStats:
    count: int = 0
    impact: dict[str, Decimal] = field(default_factory=_money_dict)       # nur bestimmbare Auswirkung
    undefined: int = 0                                                    # Befunde ohne bestimmbare Auswirkung
    affected_undefined: dict[str, Decimal] = field(default_factory=_money_dict)


@dataclass
class ProviderSummary:
    provider: str
    internal_total: int = 0
    provider_total: int = 0
    matched: int = 0
    exact: int = 0
    fuzzy: int = 0
    missing_in_provider: int = 0
    missing_in_db: int = 0
    duplicates: int = 0
    discrepancies: int = 0
    impact: dict[str, Decimal] = field(default_factory=_money_dict)
    undefined: int = 0
    affected_undefined: dict[str, Decimal] = field(default_factory=_money_dict)


@dataclass
class Summary:
    internal_total: int
    provider_total: int
    matched: int
    exact: int
    fuzzy: int
    unmatched_internal: int
    unmatched_provider: int
    duplicates: int
    discrepancy_count: int
    clean_matches: int                               # zugeordnet UND ohne jede Abweichung
    by_priority: dict[Priority, int]
    by_certainty: dict[Certainty, int]
    by_kind: dict[IssueKind, KindStats]              # nach Hauptbefund; jede Abweichung genau einmal
    net_impact: dict[str, Decimal]                   # Summe mit Vorzeichen (nur bestimmbare Auswirkung)
    gross_impact: dict[str, Decimal]                 # Summe der Beträge (Fehler heben sich nicht auf)
    undefined_count: int                             # Befunde ohne bestimmbare Auswirkung
    undefined_affected: dict[str, Decimal]           # deren betroffene Beträge – KEINE Auswirkung
    preliminary_count: int
    providers: list[ProviderSummary]

    @property
    def match_rate(self) -> float:
        """Anteil zugeordneter Buchungen an allen Datensätzen beider Seiten (Paar = 2 Datensätze)."""
        total = self.internal_total + self.provider_total
        return 2 * self.matched / total if total else 1.0

    @property
    def clean_rate(self) -> float:
        total = self.internal_total + self.provider_total
        return 2 * self.clean_matches / total if total else 1.0


def summarize(internal: list[Transaction], provider: list[Transaction], matching: MatchResult,
              discrepancies: list[Discrepancy]) -> Summary:
    providers: dict[str, ProviderSummary] = {}

    def of(code: str) -> ProviderSummary:
        return providers.setdefault(code, ProviderSummary(code))

    for tx in internal:
        of(tx.provider).internal_total += 1
    for tx in provider:
        of(tx.provider).provider_total += 1
    for match in matching.matches:
        entry = of(match.internal.provider)
        entry.matched += 1
        if match.method == "exact":
            entry.exact += 1
        else:
            entry.fuzzy += 1
    for tx in matching.unmatched_internal:
        of(tx.provider).missing_in_provider += 1
    for tx in matching.unmatched_provider:
        of(tx.provider).missing_in_db += 1
    for tx, _ in matching.duplicate_internal + matching.duplicate_provider:
        of(tx.provider).duplicates += 1

    by_kind: dict[IssueKind, KindStats] = {}
    net: dict[str, Decimal] = defaultdict(Decimal)
    gross: dict[str, Decimal] = defaultdict(Decimal)
    undefined_affected: dict[str, Decimal] = defaultdict(Decimal)
    undefined_count = 0
    for item in discrepancies:
        entry = of(item.provider_code)
        entry.discrepancies += 1
        stats = by_kind.setdefault(item.primary_kind, KindStats())
        stats.count += 1
        if item.effect_defined:
            _add(entry.impact, item.impact)
            _add(stats.impact, item.impact)
            _add(net, item.impact)
            _add(gross, item.impact, absolute=True)
        else:
            undefined_count += 1
            entry.undefined += 1
            stats.undefined += 1
            _add(entry.affected_undefined, item.affected)
            _add(stats.affected_undefined, item.affected)
            _add(undefined_affected, item.affected)

    return Summary(
        internal_total=len(internal), provider_total=len(provider),
        matched=len(matching.matches),
        exact=sum(1 for m in matching.matches if m.method == "exact"),
        fuzzy=sum(1 for m in matching.matches if m.method == "fuzzy"),
        unmatched_internal=len(matching.unmatched_internal),
        unmatched_provider=len(matching.unmatched_provider),
        duplicates=len(matching.duplicate_internal) + len(matching.duplicate_provider),
        discrepancy_count=len(discrepancies),
        clean_matches=len(matching.matches) - sum(
            1 for d in discrepancies if d.internal and d.provider and d.match is not None),
        by_priority=dict(Counter(d.priority for d in discrepancies)),
        by_certainty=dict(Counter(d.certainty for d in discrepancies)),
        by_kind=dict(sorted(by_kind.items(), key=lambda kv: list(IssueKind).index(kv[0]))),
        net_impact={c: v for c, v in net.items()}, gross_impact={c: v for c, v in gross.items()},
        undefined_count=undefined_count, undefined_affected=dict(undefined_affected),
        preliminary_count=sum(1 for d in discrepancies if d.certainty is Certainty.PRELIMINARY),
        providers=sorted(providers.values(), key=lambda p: p.provider),
    )
