import unittest
from datetime import timedelta

from tests.helpers import internal, provider
from txreconcile.config import ReconcileConfig
from txreconcile.matching import match_transactions
from txreconcile.models import Status


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
