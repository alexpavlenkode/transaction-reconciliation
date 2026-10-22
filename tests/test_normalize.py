import unittest
from datetime import timezone
from decimal import Decimal

from txreconcile import normalize as n


class ReferenceTests(unittest.TestCase):
    def test_case_whitespace_and_separators_are_ignored(self):
        self.assertEqual(n.normalize_reference(" atx-123 45 "), "ATX12345")
        self.assertEqual(n.normalize_reference("BPAY_9f3a"), n.normalize_reference("bpay_9F3A"))

    def test_empty_values(self):
        self.assertEqual(n.normalize_reference(None), "")
        self.assertEqual(n.normalize_reference("  - "), "")


class AmountTests(unittest.TestCase):
    def test_german_amount(self):
        self.assertEqual(n.parse_german_amount("1.234,56"), Decimal("1234.56"))
        self.assertEqual(n.parse_german_amount("7,5"), Decimal("7.5"))
        self.assertEqual(n.parse_german_amount("-12,00"), Decimal("-12.00"))
        self.assertEqual(n.parse_german_amount("1.000"), Decimal("1000"))  # Tausenderpunkt, keine Dezimalstelle

    def test_german_amount_rejects_garbage(self):
        for bad in ("n/a", "", "12.5", "1,2,3", "1.23,4.5", "12 EUR"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                n.parse_german_amount(bad)

    def test_minor_units_respect_currency_exponent(self):
        self.assertEqual(n.parse_minor_units(12345, "EUR"), Decimal("123.45"))
        self.assertEqual(n.parse_minor_units(15800, "JPY"), Decimal("15800"))
        self.assertEqual(n.parse_minor_units("1234", "KWD"), Decimal("1.234"))

    def test_minor_units_reject_fractions_and_bool(self):
        for bad in (12.5, True, None, "abc"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                n.parse_minor_units(bad, "EUR")

    def test_real_values_do_not_leak_float_noise(self):
        # 19.99 als REAL ist intern 19.989999...; str() liefert die kürzeste Darstellung
        self.assertEqual(n.quantize_money(n.parse_decimal(19.99), "EUR"), Decimal("19.99"))
        self.assertEqual(n.quantize_money(n.parse_decimal(0.1 + 0.2), "EUR"), Decimal("0.30"))

    def test_decimal_rejects_nan_inf_and_text(self):
        for bad in (float("nan"), float("inf"), "abc", None, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                n.parse_decimal(bad)

    def test_quantize_rounds_half_up(self):
        self.assertEqual(n.quantize_money(Decimal("2.675"), "EUR"), Decimal("2.68"))
        self.assertEqual(n.quantize_money(Decimal("1234.5"), "JPY"), Decimal("1235"))


class CurrencyTests(unittest.TestCase):
    def test_normalize_currency(self):
        self.assertEqual(n.normalize_currency(" eur "), "EUR")
        for bad in ("", None, "EURO", "E1R"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                n.normalize_currency(bad)


class TimestampTests(unittest.TestCase):
    def test_iso_with_offset_is_converted_to_utc(self):
        moment = n.parse_iso_timestamp("2025-03-03T12:15:22+02:00")
        self.assertEqual((moment.hour, moment.minute), (10, 15))
        self.assertEqual(moment.tzinfo, timezone.utc)

    def test_iso_z_suffix_and_naive_sqlite_format(self):
        self.assertEqual(n.parse_iso_timestamp("2025-03-03T10:15:22Z"), n.parse_iso_timestamp("2025-03-03 10:15:22"))

    def test_german_timestamp(self):
        self.assertEqual(n.parse_german_timestamp("03.03.2025 10:15:22").isoformat(), "2025-03-03T10:15:22+00:00")
        self.assertEqual(n.parse_german_timestamp("03.03.2025 10:15").second, 0)

    def test_invalid_timestamps(self):
        with self.assertRaises(ValueError):
            n.parse_iso_timestamp("gestern")
        with self.assertRaises(ValueError):
            n.parse_iso_timestamp("")
        with self.assertRaises(ValueError):
            n.parse_german_timestamp("2025-03-03")


if __name__ == "__main__":
    unittest.main()
