import unittest
from decimal import Decimal

from tests.helpers import internal, provider
from txreconcile.config import ReconcileConfig
from txreconcile.discrepancies import booked_amount, find_discrepancies, net_impact, prioritize
from txreconcile.importers import ImportIssue
from txreconcile.matching import match_transactions
from txreconcile.models import IssueKind, Priority, Status


def analyse(internals, providers, **cfg):
    config = ReconcileConfig(**cfg)
    return find_discrepancies(match_transactions(internals, providers, config), config)


class ImpactTests(unittest.TestCase):
    def test_only_completed_payments_are_booked(self):
        self.assertEqual(booked_amount(internal("1", "R", "10.00")), Decimal("10.00"))
        for status in (Status.PENDING, Status.FAILED, Status.REFUNDED, Status.UNKNOWN):
            self.assertEqual(booked_amount(internal("1", "R", "10.00", status=status)), 0)
        self.assertEqual(booked_amount(None), 0)

    def test_impact_is_provider_minus_database_per_currency(self):
        self.assertEqual(net_impact(internal("1", "R", "100"), provider("R", "60")), {"EUR": Decimal("-40")})
        self.assertEqual(net_impact(None, provider("R", "60")), {"EUR": Decimal("60")})
        mixed = net_impact(internal("1", "R", "100"), provider("R", "100", currency="USD"))
        self.assertEqual(mixed, {"EUR": Decimal("-100"), "USD": Decimal("100")})

    def test_no_impact_when_nothing_is_booked_on_either_side(self):
        pending = internal("1", "R", "100", status=Status.PENDING)
        failed = provider("R", "100", status=Status.FAILED)
        self.assertEqual(net_impact(pending, failed), {})


class DetectionTests(unittest.TestCase):
    def kinds(self, found):
        return [sorted(k.value for k in d.kinds) for d in found]

    def test_perfect_match_has_no_discrepancy(self):
        self.assertEqual(analyse([internal("1", "R")], [provider("R")]), [])

    def test_amount_mismatch_and_tolerance(self):
        found = analyse([internal("1", "R", "10.00")], [provider("R", "10.01")])
        self.assertEqual(self.kinds(found), [["AMOUNT_MISMATCH"]])
        self.assertEqual(found[0].impact, {"EUR": Decimal("0.01")})
        self.assertEqual(analyse([internal("1", "R", "10.00")], [provider("R", "10.01")],
                                 amount_tolerance=Decimal("0.01")), [])

    def test_status_and_amount_counted_once(self):
        found = analyse([internal("1", "R", "100")], [provider("R", "80", status=Status.PENDING)])
        self.assertEqual(self.kinds(found), [["AMOUNT_MISMATCH", "STATUS_MISMATCH"]])
        self.assertEqual(found[0].impact, {"EUR": Decimal("-100")})   # nicht -100 und -20

    def test_currency_mismatch_does_not_compare_amounts(self):
        found = analyse([internal("1", "R", "100")], [provider("R", "100", currency="USD")])
        self.assertEqual(self.kinds(found), [["CURRENCY_MISMATCH"]])
        self.assertIs(found[0].priority, Priority.HIGH)

    def test_missing_on_each_side_and_duplicates(self):
        found = analyse([internal("1", "ONLYDB"), internal("2", "BOTH"), internal("3", "BOTH")],
                        [provider("BOTH"), provider("ONLYPROV"), provider("DUP"), provider("DUP")],
                        fuzzy_enabled=False)
        kinds = {tuple(d.kinds) for d in found}
        self.assertEqual(kinds, {(IssueKind.MISSING_IN_PROVIDER,), (IssueKind.MISSING_IN_DB,),
                                 (IssueKind.DUPLICATE_IN_DB,)})
        # "DUP" kommt nur beim Anbieter vor -> beide fehlen in der DB (kein Duplikat-Befund ohne Gegenstück)
        self.assertEqual(sum(1 for d in found if d.primary_kind is IssueKind.MISSING_IN_DB), 3)

    def test_fuzzy_match_is_always_flagged_for_review(self):
        found = analyse([internal("1", "ATX-12345678")], [provider("ATX-1234567O")])
        self.assertEqual(self.kinds(found), [["REFERENCE_MISMATCH"]])
        self.assertIs(found[0].priority, Priority.LOW)

    def test_unreadable_provider_row_is_mentioned(self):
        config = ReconcileConfig()
        matching = match_transactions([internal("1", "ATX-1")], [], config)
        issue = ImportIssue("provider_a", "Zeile 3", "error", "kaputt", reference="atx-1")
        found = find_discrepancies(matching, config, [issue])
        self.assertIn("unlesbaren Datensatz", found[0].description)


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.config = ReconcileConfig()

    def test_thresholds(self):
        kinds = (IssueKind.AMOUNT_MISMATCH,)
        self.assertIs(prioritize(kinds, {"EUR": Decimal("-500")}, self.config), Priority.HIGH)
        self.assertIs(prioritize(kinds, {"EUR": Decimal("499.99")}, self.config), Priority.MEDIUM)
        self.assertIs(prioritize(kinds, {"EUR": Decimal("50")}, self.config), Priority.MEDIUM)
        self.assertIs(prioritize(kinds, {"EUR": Decimal("49.99")}, self.config), Priority.LOW)
        self.assertIs(prioritize(kinds, {}, self.config), Priority.LOW)

    def test_foreign_currency_is_weighted(self):
        kinds = (IssueKind.MISSING_IN_DB,)
        self.assertIs(prioritize(kinds, {"JPY": Decimal("15800")}, self.config), Priority.MEDIUM)   # ~96 EUR
        self.assertIs(prioritize(kinds, {"USD": Decimal("600")}, self.config), Priority.HIGH)        # ~552 EUR

    def test_results_are_sorted_by_priority_then_impact(self):
        found = analyse([internal("1", "A", "10"), internal("2", "B", "900"), internal("3", "C", "100")], [],
                        fuzzy_enabled=False)
        self.assertEqual([d.internal.record_id for d in found], ["2", "3", "1"])


if __name__ == "__main__":
    unittest.main()
