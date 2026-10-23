import random
import unittest
from datetime import timedelta
from decimal import Decimal

from tests.helpers import T0, internal, provider
from txreconcile.config import ReconcileConfig
from txreconcile.matching import match_transactions
from txreconcile.models import Status, Transaction
from txreconcile.normalize import ID_RULES, normalize_reference


def run(internals, providers, **cfg):
    return match_transactions(internals, providers, ReconcileConfig(**cfg))


class ExactMatchingTests(unittest.TestCase):
    def test_pairs_by_normalized_reference(self):
        result = run([internal("1", " atx-001 ")], [provider("ATX-001")])
        self.assertEqual([(m.internal.record_id, m.provider.record_id, m.method) for m in result.matches],
                         [("1", "ATX-001", "exact")])
        self.assertFalse(result.unmatched_internal or result.unmatched_provider)

    def test_same_reference_at_different_providers_does_not_match(self):
        result = run([internal("1", "REF1", provider="B")], [provider("REF1")], fuzzy_enabled=False)
        self.assertEqual(len(result.matches), 0)
        self.assertEqual(len(result.unmatched_internal), 1)
        self.assertEqual(len(result.unmatched_provider), 1)

    def test_internal_without_reference_stays_unmatched(self):
        result = run([internal("1", None)], [provider("ATX-001")])
        self.assertEqual(len(result.unmatched_internal), 1)
        self.assertEqual(len(result.unmatched_provider), 1)

    def test_duplicates_in_provider_pair_with_closest_and_flag_surplus(self):
        first, second = provider("ATX-001", minutes=1), provider("ATX-001", minutes=4)
        result = run([internal("1", "ATX-001")], [second, first])
        self.assertEqual(len(result.matches), 1)
        self.assertIs(result.matches[0].provider, first)
        self.assertEqual([tx for tx, _ in result.duplicate_provider], [second])

    def test_duplicates_in_db_prefer_equal_amount_over_closer_time(self):
        wrong_amount = internal("1", "ATX-001", "90.00", minutes=0)
        right_amount = internal("2", "ATX-001", "100.00", minutes=30)
        result = run([wrong_amount, right_amount], [provider("ATX-001", "100.00")])
        self.assertEqual(result.matches[0].internal.record_id, "2")
        self.assertEqual([tx.record_id for tx, _ in result.duplicate_internal], ["1"])

    def test_duplicates_are_never_fuzzy_matched_again(self):
        result = run([internal("1", "ATX-001")], [provider("ATX-001"), provider("ATX-001", minutes=1)])
        self.assertEqual(len(result.duplicate_provider), 1)
        self.assertEqual(len(result.matches), 1)

    def test_each_record_is_used_at_most_once(self):
        internals = [internal(str(i), f"REF{i:04d}") for i in range(20)]
        providers = [provider(f"REF{i:04d}") for i in range(20)]
        result = run(internals, providers)
        self.assertEqual(len({m.internal.record_id for m in result.matches}), 20)
        self.assertEqual(len({m.provider.record_id for m in result.matches}), 20)


class IdRuleTests(unittest.TestCase):
    """Die Schlüssel bildet der Importer nach der ID-Regel des Anbieters; das Matching vergleicht nur Schlüssel."""

    def test_case_sensitive_provider_does_not_merge_ids_that_differ_only_in_case(self):
        rule = ID_RULES["B"]
        db = Transaction(source="internal", provider="B", record_id="1", reference="BPAY_X", amount=Decimal("5"),
                         currency="EUR", status=Status.COMPLETED, timestamp=T0, key=normalize_reference("BPAY_X", rule))
        prov = Transaction(source="provider_b", provider="B", record_id="bpay_x", reference="bpay_x",
                           amount=Decimal("5"), currency="EUR", status=Status.COMPLETED, timestamp=T0,
                           key=normalize_reference("bpay_x", rule))
        result = run([db], [prov], fuzzy_enabled=False)
        self.assertEqual(result.matches, [])                       # exakte Regel: BPAY_X ist nicht bpay_x
        self.assertEqual((len(result.unmatched_internal), len(result.unmatched_provider)), (1, 1))

    def test_case_insensitive_provider_merges_them(self):
        result = run([internal("1", "atx-1 ")], [provider("ATX1")], fuzzy_enabled=False)
        self.assertEqual(len(result.matches), 1)


class OrderIndependenceTests(unittest.TestCase):
    def test_matching_does_not_depend_on_input_order(self):
        internals = [internal(str(i), f"REF{i % 4}", "100.00", minutes=i) for i in range(12)]
        providers = [provider(f"REF{i % 4}", "100.00", minutes=i * 2) for i in range(10)]
        baseline = run(internals, providers)
        pairs = lambda r: sorted((m.internal.record_id, m.provider.timestamp.isoformat()) for m in r.matches)
        for seed in range(5):
            shuffled_i, shuffled_p = internals[:], providers[:]
            random.Random(seed).shuffle(shuffled_i)
            random.Random(seed + 100).shuffle(shuffled_p)
            again = run(shuffled_i, shuffled_p)
            self.assertEqual(pairs(again), pairs(baseline))
            self.assertEqual(sorted(t.record_id for t, _ in again.duplicate_internal),
                             sorted(t.record_id for t, _ in baseline.duplicate_internal))


class FuzzyMatchingTests(unittest.TestCase):
    def test_typo_in_reference_is_matched_fuzzily(self):
        result = run([internal("1", "ATX-12345678")], [provider("ATX-1234567O", minutes=2)])
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.matches[0].method, "fuzzy")
        self.assertGreater(result.matches[0].confidence, 0.9)

    def test_fuzzy_can_be_disabled(self):
        result = run([internal("1", "ATX-12345678")], [provider("ATX-1234567O")], fuzzy_enabled=False)
        self.assertEqual(result.matches, [])

    def test_similar_reference_but_very_different_amount_is_not_matched(self):
        # Schutz gegen falsche Treffer: fast gleiche Referenz, aber völlig anderer Betrag
        result = run([internal("1", "ATX-12345670", "1800.00")], [provider("ATX-12345671", "640.00")])
        self.assertEqual(result.matches, [])

    def test_differing_amount_requires_a_near_identical_reference(self):
        # Referenz-Ähnlichkeit 0,91: reicht bei gleichem Betrag, aber nicht, wenn auch der Betrag abweicht
        self.assertEqual(len(run([internal("1", "ATX-12345670", "100.00")], [provider("ATX-12345671", "100.00")]).matches), 1)
        self.assertEqual(run([internal("1", "ATX-12345670", "100.00")], [provider("ATX-12345671", "90.00")]).matches, [])
        # Ähnlichkeit 0,95: auch mit leicht abweichendem Betrag zuordenbar
        self.assertEqual(len(run([internal("1", "ATX-12345678", "100.00")], [provider("TX-12345678", "92.00")]).matches), 1)

    def test_outside_time_window_is_not_matched(self):
        result = run([internal("1", "ATX-12345678")], [provider("ATX-1234567O", minutes=5 * 24 * 60)])
        self.assertEqual(result.matches, [])
        result = run([internal("1", "ATX-12345678")], [provider("ATX-1234567O", minutes=5 * 24 * 60)],
                     fuzzy_time_window=timedelta(days=10))
        self.assertEqual(len(result.matches), 1)

    def test_different_currency_is_not_fuzzy_matched(self):
        result = run([internal("1", "ATX-12345678")], [provider("ATX-1234567O", currency="USD")])
        self.assertEqual(result.matches, [])

    def test_assignment_is_one_to_one_and_prefers_best_score(self):
        internals = [internal("1", "ATX-12345678")]
        providers = [provider("ATX-1234567O", minutes=30), provider("ATX-1234567X", minutes=1)]
        result = run(internals, providers)
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.matches[0].provider.record_id, "ATX-1234567X")   # zeitlich näher -> besserer Score
        self.assertEqual(len(result.unmatched_provider), 1)

    def test_fuzzy_only_uses_leftovers(self):
        result = run([internal("1", "ATX-12345678"), internal("2", "ATX-12345679")],
                     [provider("ATX-12345678"), provider("ATX-1234567O")])
        methods = {m.internal.record_id: m.method for m in result.matches}
        self.assertEqual(methods, {"1": "exact", "2": "fuzzy"})


if __name__ == "__main__":
    unittest.main()
