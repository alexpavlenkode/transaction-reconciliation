import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers import T0, internal, provider
from txreconcile.config import ReconcileConfig
from txreconcile.discrepancies import (affected_amount, booked_amount, find_discrepancies, is_due, level,
                                       net_impact)
from txreconcile.importers import ImportIssue
from txreconcile.matching import match_transactions
from txreconcile.models import Certainty, IssueKind, Priority, Status

UTC = timezone.utc


def analyse(internals, providers, issues=None, **cfg):
    config = ReconcileConfig(**cfg)
    return find_discrepancies(match_transactions(internals, providers, config), config, issues)


class ImpactTests(unittest.TestCase):
    def test_only_completed_payments_are_booked(self):
        self.assertEqual(booked_amount(internal("1", "R", "10.00")), Decimal("10.00"))
        for status in (Status.PENDING, Status.FAILED, Status.REFUNDED):
            self.assertEqual(booked_amount(internal("1", "R", "10.00", status=status)), 0)
        self.assertEqual(booked_amount(None), 0)

    def test_impact_is_provider_minus_database_per_currency(self):
        self.assertEqual(net_impact(internal("1", "R", "100"), provider("R", "60")), {"EUR": Decimal("-40")})
        self.assertEqual(net_impact(None, provider("R", "60")), {"EUR": Decimal("60")})

    def test_no_impact_when_nothing_is_booked_on_either_side(self):
        pending = internal("1", "R", "100", status=Status.PENDING)
        failed = provider("R", "100", status=Status.FAILED)
        self.assertEqual(net_impact(pending, failed), {})

    def test_affected_amount_is_the_larger_amount_per_currency(self):
        self.assertEqual(affected_amount(internal("1", "R", "100"), provider("R", "60")), {"EUR": Decimal("100")})
        mixed = affected_amount(internal("1", "R", "100"), provider("R", "80", currency="USD"))
        self.assertEqual(mixed, {"EUR": Decimal("100"), "USD": Decimal("80")})


class DetectionTests(unittest.TestCase):
    def kinds(self, found):
        return [sorted(k.value for k in d.kinds) for d in found]

    def test_perfect_match_has_no_discrepancy(self):
        self.assertEqual(analyse([internal("1", "R")], [provider("R")]), [])

    def test_amount_mismatch_and_tolerance(self):
        found = analyse([internal("1", "R", "10.00")], [provider("R", "10.01")])
        self.assertEqual(self.kinds(found), [["AMOUNT_MISMATCH"]])
        self.assertEqual(found[0].impact, {"EUR": Decimal("0.01")})
        self.assertIs(found[0].certainty, Certainty.CALCULATED)
        self.assertEqual(analyse([internal("1", "R", "10.00")], [provider("R", "10.01")],
                                 amount_tolerance=Decimal("0.01")), [])

    def test_status_and_amount_counted_once(self):
        found = analyse([internal("1", "R", "100")], [provider("R", "80", status=Status.PENDING)])
        self.assertEqual(self.kinds(found), [["AMOUNT_MISMATCH", "STATUS_MISMATCH"]])
        self.assertEqual(found[0].impact, {"EUR": Decimal("-100")})   # nicht -100 und -20

    def test_fuzzy_match_is_always_flagged_for_review(self):
        found = analyse([internal("1", "ATX-12345678")], [provider("ATX-1234567O")])
        self.assertEqual(self.kinds(found), [["REFERENCE_MISMATCH"]])
        self.assertIs(found[0].priority, Priority.LOW)

    def test_missing_on_each_side_and_duplicates(self):
        found = analyse([internal("1", "ONLYDB"), internal("2", "BOTH"), internal("3", "BOTH")],
                        [provider("BOTH"), provider("ONLYPROV"), provider("DUP"), provider("DUP")],
                        fuzzy_enabled=False)
        kinds = {tuple(d.kinds) for d in found}
        self.assertEqual(kinds, {(IssueKind.MISSING_IN_PROVIDER,), (IssueKind.MISSING_IN_DB,),
                                 (IssueKind.DUPLICATE_IN_DB,)})
        # "DUP" kommt nur beim Anbieter vor -> beide fehlen in der DB (kein Duplikat-Befund ohne Gegenstück)
        self.assertEqual(sum(1 for d in found if d.primary_kind is IssueKind.MISSING_IN_DB), 3)


class UndefinedEffectTests(unittest.TestCase):
    """Wo die Auswirkung nicht bestimmbar ist, gibt es nur den betroffenen Betrag – keine erfundene Summe."""

    def test_unknown_status_is_not_treated_as_zero(self):
        found = analyse([internal("1", "R", "330")], [provider("R", "330", status=Status.UNKNOWN)])
        self.assertEqual(found[0].certainty, Certainty.UNDEFINED)
        self.assertEqual(found[0].impact, {})                          # kein -330
        self.assertEqual(found[0].affected, {"EUR": Decimal("330")})
        self.assertIs(found[0].priority, Priority.MEDIUM)              # Schwere nach dem betroffenen Betrag
        self.assertIn("unbekannt", found[0].description)

    def test_unknown_status_on_a_single_record_is_also_undefined(self):
        found = analyse([], [provider("R", "700", status=Status.UNKNOWN)])
        self.assertEqual((found[0].certainty, found[0].impact), (Certainty.UNDEFINED, {}))
        self.assertIs(found[0].priority, Priority.HIGH)

    def test_currency_mismatch_is_high_and_undefined(self):
        found = analyse([internal("1", "R", "100")], [provider("R", "100", currency="USD")])
        self.assertEqual([k.value for k in found[0].kinds], ["CURRENCY_MISMATCH"])
        self.assertEqual((found[0].certainty, found[0].impact), (Certainty.UNDEFINED, {}))
        self.assertEqual(found[0].affected, {"EUR": Decimal("100"), "USD": Decimal("100")})
        self.assertIs(found[0].priority, Priority.HIGH)

    def test_duplicate_has_affected_amount_but_no_effect_and_can_still_be_high(self):
        found = analyse([internal("1", "R", "900")], [provider("R", "900", minutes=1), provider("R", "900", minutes=4)])
        self.assertEqual([k.value for k in found[0].kinds], ["DUPLICATE_IN_PROVIDER"])
        self.assertEqual((found[0].certainty, found[0].impact), (Certainty.UNDEFINED, {}))
        self.assertEqual(found[0].affected, {"EUR": Decimal("900")})
        self.assertIs(found[0].priority, Priority.HIGH)                # groß und unklar -> hoch

    def test_equal_reference_with_different_spelling_is_flagged_as_possible_collision(self):
        found = analyse([internal("1", "ATX-1")], [provider("ATX-1", minutes=1), provider("atx1", minutes=4)])
        self.assertEqual(sorted(k.value for k in found[0].kinds), ["DUPLICATE_IN_PROVIDER", "ID_COLLISION"])
        self.assertIn("Kollision", found[0].description)

    def test_pure_duplicates_with_identical_reference_are_not_called_collisions(self):
        found = analyse([internal("1", "ATX-1")], [provider("ATX-1", minutes=1), provider("ATX-1", minutes=4)])
        self.assertNotIn(IssueKind.ID_COLLISION, found[0].kinds)

    def test_undefined_cases_are_excluded_from_the_summed_effect(self):
        from txreconcile.summary import summarize
        config = ReconcileConfig()
        matching = match_transactions([internal("1", "R", "100"), internal("2", "S", "50")],
                                      [provider("R", "100", currency="USD"), provider("S", "20")], config)
        found = find_discrepancies(matching, config)
        summary = summarize([internal("1", "R"), internal("2", "S")], [], matching, found)
        self.assertEqual(summary.net_impact, {"EUR": Decimal("-30")})           # nur der berechenbare Betragsfehler
        self.assertEqual(summary.undefined_count, 1)
        self.assertEqual(summary.undefined_affected, {"EUR": Decimal("100"), "USD": Decimal("100")})


class DueDateTests(unittest.TestCase):
    def setUp(self):
        self.booked = internal("1", "R", "100")          # gebucht am T0
        self.lag = timedelta(days=3)

    def config(self, as_of):
        return ReconcileConfig(as_of=as_of, settlement_lag=self.lag)

    def test_boundary_is_strict(self):
        # überfällig genau dann, wenn as_of > Buchungszeit + Frist
        self.assertFalse(is_due(self.booked, self.config(T0 + self.lag)))
        self.assertTrue(is_due(self.booked, self.config(T0 + self.lag + timedelta(seconds=1))))
        self.assertFalse(is_due(self.booked, self.config(T0 + self.lag - timedelta(seconds=1))))

    def test_without_as_of_everything_is_due(self):
        self.assertTrue(is_due(self.booked, ReconcileConfig()))

    def test_not_yet_due_is_low_undefined_and_overdue_is_at_least_medium(self):
        early = analyse([internal("1", "R", "10")], [], as_of=T0 + timedelta(days=1))
        self.assertEqual(([k.value for k in early[0].kinds], early[0].priority, early[0].certainty),
                         (["NOT_YET_DUE"], Priority.LOW, Certainty.UNDEFINED))
        late = analyse([internal("1", "R", "10")], [], as_of=T0 + timedelta(days=4))
        self.assertEqual(([k.value for k in late[0].kinds], late[0].priority, late[0].certainty),
                         (["MISSING_IN_PROVIDER"], Priority.MEDIUM, Certainty.CALCULATED))   # klein, aber überfällig
        self.assertEqual(late[0].impact, {"EUR": Decimal("-10")})

    def test_pending_booking_missing_after_the_deadline_is_flagged(self):
        late = analyse([internal("1", "R", "10", status=Status.PENDING)], [], as_of=T0 + timedelta(days=4))
        self.assertIs(late[0].priority, Priority.MEDIUM)
        self.assertEqual(late[0].impact, {})


class UnreadableRowTests(unittest.TestCase):
    def test_unreadable_provider_row_with_known_key_makes_pair_unverifiable_not_missing(self):
        issue = ImportIssue("provider_a", "Zeile 3", "error", "Betrag kaputt", "atx-1", "A", "ATX1")
        found = analyse([internal("1", "ATX-1", "410")], [], [issue])
        self.assertEqual([k.value for k in found[0].kinds], ["SOURCE_ROW_UNREADABLE"])
        self.assertEqual((found[0].certainty, found[0].impact), (Certainty.UNDEFINED, {}))
        self.assertEqual(found[0].affected, {"EUR": Decimal("410")})
        self.assertIn("Zeile 3", found[0].description)

    def test_unreadable_internal_row_makes_the_provider_record_unverifiable(self):
        issue = ImportIssue("internal", "id=7", "error", "kaputt", "ATX-1", None, "ATX1")
        found = analyse([], [provider("ATX-1", "75")], [issue])
        self.assertEqual([k.value for k in found[0].kinds], ["SOURCE_ROW_UNREADABLE"])

    def test_unreadable_row_of_another_provider_does_not_apply(self):
        issue = ImportIssue("provider_b", "Zeile 3", "error", "kaputt", "atx-1", "B", "ATX1")
        found = analyse([internal("1", "ATX-1", "410")], [], [issue])
        self.assertEqual([k.value for k in found[0].kinds], ["MISSING_IN_PROVIDER"])

    def test_unreadable_row_without_reference_makes_missing_findings_preliminary(self):
        issue = ImportIssue("provider_a", "Zeile 9", "error", "ID fehlt", None, "A", "")
        found = analyse([internal("1", "X1", "100")], [provider("Y1", "50")], [issue])
        by_kind = {d.primary_kind: d for d in found}
        self.assertIs(by_kind[IssueKind.MISSING_IN_PROVIDER].certainty, Certainty.PRELIMINARY)
        self.assertEqual(by_kind[IssueKind.MISSING_IN_PROVIDER].impact, {"EUR": Decimal("-100")})  # berechnet, aber vorläufig
        self.assertIs(by_kind[IssueKind.MISSING_IN_DB].certainty, Certainty.CALCULATED)              # andere Seite unberührt
        self.assertIn("Vorläufig", by_kind[IssueKind.MISSING_IN_PROVIDER].description)

    def test_warnings_do_not_taint_results(self):
        warning = ImportIssue("provider_a", "Zeile 9", "warning", "Status unbekannt", None, "A", "")
        found = analyse([internal("1", "X1", "100")], [], [warning])
        self.assertIs(found[0].certainty, Certainty.CALCULATED)


class SeverityTests(unittest.TestCase):
    def test_thresholds_apply_per_currency_without_conversion(self):
        config = ReconcileConfig()
        self.assertIs(level({"EUR": Decimal("-500")}, config), Priority.HIGH)
        self.assertIs(level({"EUR": Decimal("499.99")}, config), Priority.MEDIUM)
        self.assertIs(level({"EUR": Decimal("50")}, config), Priority.MEDIUM)
        self.assertIs(level({"EUR": Decimal("49.99")}, config), Priority.LOW)
        self.assertIs(level({}, config), Priority.LOW)
        # JPY hat eigene Schwellen (75.000 / 7.500): 15.800 JPY ist mittel, nicht "hoch" wie 15.800 EUR
        self.assertIs(level({"JPY": Decimal("15800")}, config), Priority.MEDIUM)
        self.assertIs(level({"EUR": Decimal("15800")}, config), Priority.HIGH)
        self.assertIs(level({"JPY": Decimal("80000")}, config), Priority.HIGH)

    def test_configurable_thresholds_and_highest_currency_wins(self):
        config = ReconcileConfig(currency_thresholds={"USD": (Decimal("100"), Decimal("10"))})
        self.assertIs(level({"USD": Decimal("150")}, config), Priority.HIGH)
        self.assertIs(level({"USD": Decimal("20"), "EUR": Decimal("1")}, config), Priority.MEDIUM)

    def test_results_are_sorted_by_priority_then_size(self):
        found = analyse([internal("1", "A", "100"), internal("2", "B", "900"), internal("3", "C", "60")], [],
                        fuzzy_enabled=False)
        self.assertEqual([d.internal.record_id for d in found], ["2", "1", "3"])


if __name__ == "__main__":
    unittest.main()
