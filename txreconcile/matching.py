"""Zuordnung interner Buchungen zu Anbieter-Einträgen.

Zweistufig:

1. **Exakt** – gleicher Anbieter und gleicher normalisierter Referenzschlüssel. Das ist der
   Normalfall und läuft in O(n) über Hash-Gruppen. Mehrfache Einträge mit demselben Schlüssel
   (Duplikate) werden paarweise zugeordnet; der Überschuss wird als Duplikat markiert und
   *nicht* erneut unscharf zugeordnet.
2. **Unscharf (optional)** – nur für die Reste: gleicher Anbieter + gleiche Währung, Zeitfenster,
   Referenz-Ähnlichkeit. Der Score kombiniert Referenz, Betrag und Zeitnähe; die Zuordnung ist
   strikt 1:1 und gierig nach dem besten Score (deterministisch bei Gleichstand).

Ein unscharfer Treffer ist nie "stillschweigend": er wird im Bericht als Zuordnung zur Prüfung geführt.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

from .config import ReconcileConfig
from .models import Match, Transaction


@dataclass
class MatchResult:
    matches: list[Match] = field(default_factory=list)
    unmatched_internal: list[Transaction] = field(default_factory=list)
    unmatched_provider: list[Transaction] = field(default_factory=list)
    duplicate_internal: list[tuple[Transaction, Match]] = field(default_factory=list)
    duplicate_provider: list[tuple[Transaction, Match]] = field(default_factory=list)


def match_transactions(internal: list[Transaction], provider: list[Transaction],
                       config: ReconcileConfig) -> MatchResult:
    result = _match_exact(internal, provider)
    if config.fuzzy_enabled and result.unmatched_internal and result.unmatched_provider:
        fuzzy, left_internal, left_provider = _match_fuzzy(
            result.unmatched_internal, result.unmatched_provider, config)
        result.matches.extend(fuzzy)
        result.unmatched_internal, result.unmatched_provider = left_internal, left_provider
    return result


# ---------------------------------------------------------------------------
# Stufe 1: exakt
# ---------------------------------------------------------------------------

def _group(transactions: list[Transaction]) -> tuple[dict[tuple[str, str], list[Transaction]], list[Transaction]]:
    groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    without_key: list[Transaction] = []
    for tx in transactions:
        if tx.key:
            groups[(tx.provider, tx.key)].append(tx)
        else:
            without_key.append(tx)           # z. B. interne Buchung ohne Provider-Referenz
    return groups, without_key


def _match_exact(internal: list[Transaction], provider: list[Transaction]) -> MatchResult:
    result = MatchResult()
    internal_groups, internal_no_key = _group(internal)
    provider_groups, provider_no_key = _group(provider)
    result.unmatched_internal.extend(internal_no_key)
    result.unmatched_provider.extend(provider_no_key)

    for group_key, internal_items in internal_groups.items():
        provider_items = provider_groups.get(group_key)
        if not provider_items:
            result.unmatched_internal.extend(internal_items)
            continue
        pairs, extra_internal, extra_provider = _pair_group(internal_items, provider_items)
        matches = [Match(i, p, "exact") for i, p in pairs]
        result.matches.extend(matches)
        result.duplicate_internal.extend((tx, matches[0]) for tx in extra_internal)
        result.duplicate_provider.extend((tx, matches[0]) for tx in extra_provider)

    for group_key, provider_items in provider_groups.items():
        if group_key not in internal_groups:
            result.unmatched_provider.extend(provider_items)
    return result


def _pair_group(internal_items: list[Transaction], provider_items: list[Transaction]):
    """Paart Einträge mit identischem Schlüssel; bei Mehrfachtreffern gewinnt das ähnlichste Paar.

    Kosten = (Währung verschieden, Betragsdifferenz, Zeitabstand): gleiche Beträge und nahe
    Zeitpunkte werden bevorzugt gepaart, damit ein Duplikat nicht das "falsche" Original erwischt.
    """
    if len(internal_items) == 1 and len(provider_items) == 1:
        return [(internal_items[0], provider_items[0])], [], []
    costs = sorted(
        (_pair_cost(i, p), ii, pi)
        for ii, i in enumerate(internal_items) for pi, p in enumerate(provider_items))
    used_i: set[int] = set()
    used_p: set[int] = set()
    pairs = []
    for _, ii, pi in costs:
        if ii in used_i or pi in used_p:
            continue
        used_i.add(ii)
        used_p.add(pi)
        pairs.append((internal_items[ii], provider_items[pi]))
    extra_i = [t for n, t in enumerate(internal_items) if n not in used_i]
    extra_p = [t for n, t in enumerate(provider_items) if n not in used_p]
    return pairs, extra_i, extra_p


def _pair_cost(i: Transaction, p: Transaction) -> tuple[int, Decimal, float]:
    return (int(i.currency != p.currency),
            abs(i.amount - p.amount) if i.currency == p.currency else Decimal(0),
            abs((i.timestamp - p.timestamp).total_seconds()))


# ---------------------------------------------------------------------------
# Stufe 2: unscharf
# ---------------------------------------------------------------------------

def _score(matcher: SequenceMatcher, i: Transaction, p: Transaction,
           config: ReconcileConfig) -> tuple[float, float] | None:
    """(Gesamtscore, Referenzähnlichkeit) oder ``None``, wenn das Paar nicht infrage kommt.

    ``matcher`` ist auf die Referenz von ``i`` als *seq2* vorbereitet: difflib cached seq2, daher wird
    die teure Indexierung pro interner Buchung nur einmal statt pro Kandidatenpaar gemacht.
    """
    threshold = config.fuzzy_min_ref_similarity
    matcher.set_seq1(p.key)
    # Billige obere Schranken zuerst: verhindert in den meisten Fällen die teure ratio()-Berechnung.
    if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
        return None
    ref_similarity = matcher.ratio()
    if ref_similarity < threshold:
        return None

    if i.amount == p.amount:
        amount_similarity = 1.0
    elif ref_similarity < config.fuzzy_min_ref_similarity_if_amount_differs:
        return None
    else:
        amount_similarity = max(0.0, 1.0 - float(abs(i.amount - p.amount) / max(abs(i.amount), abs(p.amount))))
    window = max(config.fuzzy_time_window.total_seconds(), 1.0)
    time_similarity = max(0.0, 1.0 - abs((i.timestamp - p.timestamp).total_seconds()) / window)

    score = 0.6 * ref_similarity + 0.3 * amount_similarity + 0.1 * time_similarity
    return (score, ref_similarity) if score >= config.fuzzy_min_score else None


def _match_fuzzy(unmatched_internal: list[Transaction], unmatched_provider: list[Transaction],
                 config: ReconcileConfig):
    # Blocking: nur Kandidaten desselben Anbieters/derselben Währung innerhalb des Zeitfensters werden
    # verglichen (sortierte Liste + Bisektion) – statt des vollen Kreuzprodukts O(n·m).
    blocks: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for index, tx in enumerate(unmatched_provider):
        if tx.key:
            blocks[(tx.provider, tx.currency)].append((tx.timestamp, index))
    stamps: dict[tuple[str, str], list] = {}
    for block_key, block in blocks.items():
        block.sort()
        stamps[block_key] = [moment for moment, _ in block]

    window = config.fuzzy_time_window
    candidates: list[tuple[float, int, int, float]] = []
    for ii, internal in enumerate(unmatched_internal):
        block_key = (internal.provider, internal.currency)
        if not internal.key or block_key not in blocks:
            continue
        lo = bisect_left(stamps[block_key], internal.timestamp - window)
        hi = bisect_right(stamps[block_key], internal.timestamp + window)
        if lo == hi:
            continue
        matcher = SequenceMatcher(None, autojunk=False)
        matcher.set_seq2(internal.key)
        for _, pi in blocks[block_key][lo:hi]:
            scored = _score(matcher, internal, unmatched_provider[pi], config)
            if scored:
                candidates.append((-scored[0], ii, pi, scored[1]))

    candidates.sort()                         # bester Score zuerst, danach Indizes -> deterministisch
    used_i: set[int] = set()
    used_p: set[int] = set()
    matches: list[Match] = []
    for neg_score, ii, pi, _ in candidates:
        if ii in used_i or pi in used_p:
            continue
        used_i.add(ii)
        used_p.add(pi)
        matches.append(Match(unmatched_internal[ii], unmatched_provider[pi], "fuzzy", round(-neg_score, 3)))

    left_internal = [t for n, t in enumerate(unmatched_internal) if n not in used_i]
    left_provider = [t for n, t in enumerate(unmatched_provider) if n not in used_p]
    return matches, left_internal, left_provider
