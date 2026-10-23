import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests.helpers import DATA
from tests.test_normalize import has_tzdata
from txreconcile.importers import (InternalDbImporter, ProviderACsvImporter, ProviderBJsonImporter, SourceError)
from txreconcile.models import Status
from txreconcile.normalize import ID_RULES, normalize_reference

CSV_HEADER = "Transaktions-ID;Zeitstempel (UTC);Betrag;Waehrung;Status\n"


class SampleDataImportTests(unittest.TestCase):
    def test_internal_db(self):
        result = InternalDbImporter().read(DATA / "internal.db")
        self.assertEqual(len(result.transactions), result.rows_read)
        self.assertEqual(result.issues, [])
        first = result.transactions[0]
        self.assertEqual(first.source, "internal")
        self.assertIsInstance(first.amount, Decimal)
        self.assertIsNotNone(first.timestamp.tzinfo)

    def test_internal_keys_follow_the_provider_rule(self):
        by_provider = {}
        for tx in InternalDbImporter().read(DATA / "internal.db").transactions:
            if tx.reference:
                self.assertEqual(tx.key, normalize_reference(tx.reference, ID_RULES[tx.provider]))
                by_provider.setdefault(tx.provider, tx)
        self.assertEqual(by_provider["A"].key, by_provider["A"].key.upper())      # A: ohne Groß-/Kleinschreibung
        self.assertEqual(by_provider["B"].key, by_provider["B"].reference.strip())  # B: exakt

    def test_provider_a_csv_parses_german_format_and_reports_bad_row(self):
        result = ProviderACsvImporter().read(DATA / "provider_a.csv")
        self.assertEqual(result.rows_read, 31)             # Leerzeile am Ende zählt nicht
        self.assertEqual(len(result.transactions), 30)
        self.assertEqual([(i.severity, i.location.startswith("Zeile")) for i in result.issues], [("error", True)])
        self.assertIn("n/a", result.issues[0].message)
        self.assertTrue(result.issues[0].key)              # ID lesbar: Verknüpfung mit der Gegenseite bleibt möglich

    def test_provider_b_json_minor_units_and_issues(self):
        result = ProviderBJsonImporter().read(DATA / "provider_b.json")
        self.assertEqual(result.rows_read, 17)
        self.assertEqual(len(result.transactions), 16)     # ein Eintrag ohne id
        self.assertEqual(sorted(i.severity for i in result.issues), ["error", "warning"])
        keyless = [i for i in result.errors if not i.key]
        self.assertEqual(len(keyless), 1)                  # Fehler ohne lesbare ID
        yen = [t for t in result.transactions if t.currency == "JPY"]
        self.assertEqual([t.amount for t in yen], [Decimal("15800")])
        unknown = [t for t in result.transactions if t.status is Status.UNKNOWN]
        self.assertEqual([t.raw_status for t in unknown], ["chargeback_initiated"])

    def test_provider_b_offsets_are_normalized_to_utc(self):
        for t in ProviderBJsonImporter().read(DATA / "provider_b.json").transactions:
            self.assertEqual(t.timestamp.utcoffset().total_seconds(), 0)


class FatalErrorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, name: str, content: str, encoding="utf-8") -> Path:
        path = self.tmp / name
        path.write_text(content, encoding=encoding)
        return path

    def make_db(self, name: str, ddl: str, *rows) -> Path:
        path = self.tmp / name
        conn = sqlite3.connect(path)
        with conn:
            conn.execute(ddl)
            for row in rows:
                conn.execute(f"INSERT INTO transactions VALUES ({','.join('?' * len(row))})", row)
        conn.close()
        return path

    def test_missing_files(self):
        for importer in (InternalDbImporter(), ProviderACsvImporter(), ProviderBJsonImporter()):
            with self.subTest(importer=type(importer).__name__), self.assertRaises(SourceError):
                importer.read(self.tmp / "gibt-es-nicht")

    def test_not_a_database(self):
        with self.assertRaises(SourceError):
            InternalDbImporter().read(self.write("x.db", "das ist keine datenbank" * 50))

    def test_database_without_table_or_columns(self):
        empty = self.tmp / "empty.db"
        sqlite3.connect(empty).close()
        with self.assertRaisesRegex(SourceError, "transactions"):
            InternalDbImporter().read(empty)
        partial = self.make_db("partial.db", "CREATE TABLE transactions (id INTEGER)")
        with self.assertRaisesRegex(SourceError, "Spalten fehlen"):
            InternalDbImporter().read(partial)

    def test_csv_with_wrong_header(self):
        with self.assertRaisesRegex(SourceError, "Spalten fehlen"):
            ProviderACsvImporter().read(self.write("a.csv", "foo;bar\n1;2\n"))

    def test_csv_with_invalid_encoding(self):
        path = self.tmp / "a.csv"
        path.write_bytes(b"Transaktions-ID;Zeitstempel (UTC);Betrag;Waehrung;Status\n\xff\xfe;;;;\n")
        with self.assertRaises(SourceError):
            ProviderACsvImporter().read(path)

    def test_json_invalid_or_wrong_shape(self):
        with self.assertRaises(SourceError):
            ProviderBJsonImporter().read(self.write("b.json", "{nicht json"))
        with self.assertRaisesRegex(SourceError, "transactions"):
            ProviderBJsonImporter().read(self.write("b2.json", json.dumps({"foo": []})))
        with self.assertRaises(SourceError):
            ProviderBJsonImporter().read(self.write("b3.json", json.dumps([1, 2])))

    def test_unknown_csv_timezone_is_fatal(self):
        path = self.write("a.csv", CSV_HEADER)
        with self.assertRaisesRegex(SourceError, "Zeitzone"):
            ProviderACsvImporter(csv_timezone="Mars/Olympus_Mons").read(path)


class StrictAmountTests(unittest.TestCase):
    """Beträge: Minor Units sind der Vertrag; REAL ist nur ein ausdrücklicher Altbestands-Modus."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def make_db(self, ddl, *rows):
        path = self.tmp / "i.db"
        conn = sqlite3.connect(path)
        with conn:
            conn.execute(ddl)
            for row in rows:
                conn.execute(f"INSERT INTO transactions VALUES ({','.join('?' * len(row))})", row)
        conn.close()
        return path

    STRICT = ("CREATE TABLE transactions (id INTEGER PRIMARY KEY, provider TEXT, provider_ref TEXT, "
              "amount_minor INTEGER, currency TEXT, status TEXT, created_at TEXT)")
    LEGACY = ("CREATE TABLE transactions (id INTEGER PRIMARY KEY, provider TEXT, provider_ref TEXT, "
              "amount REAL, currency TEXT, status TEXT, created_at TEXT)")

    def test_minor_units_are_exact(self):
        path = self.make_db(self.STRICT, (1, "A", "x", 1999, "EUR", "completed", "2025-03-03 10:00:00"),
                            (2, "B", "y", 15800, "JPY", "completed", "2025-03-03 10:00:00"))
        result = InternalDbImporter().read(path)
        self.assertEqual([t.amount for t in result.transactions], [Decimal("19.99"), Decimal("15800")])

    def test_non_integer_value_in_amount_minor_is_a_row_error(self):
        # (SQLite wandelt "1999" in einer INTEGER-Spalte selbst in 1999 um – das ist dann tatsächlich ein INTEGER)
        path = self.make_db(self.STRICT, (1, "A", "x", 19.99, "EUR", "completed", "2025-03-03 10:00:00"),
                            (2, "A", "z", "19,99", "EUR", "completed", "2025-03-03 10:00:00"),   # Text bleibt Text
                            (3, "A", "w", 500, "EUR", "completed", "2025-03-03 10:00:00"))
        result = InternalDbImporter().read(path)
        self.assertEqual([t.record_id for t in result.transactions], ["3"])
        self.assertEqual(len(result.errors), 2)
        self.assertTrue(all(i.key for i in result.errors))      # IDs lesbar -> Gegenseite wird "nicht prüfbar"

    def test_real_column_is_refused_by_default(self):
        path = self.make_db(self.LEGACY, (1, "A", "x", 19.99, "EUR", "completed", "2025-03-03 10:00:00"))
        with self.assertRaisesRegex(SourceError, "amount_minor.*allow-real-amount"):
            InternalDbImporter().read(path)

    def test_real_column_with_explicit_legacy_mode_is_rounded_and_warned(self):
        path = self.make_db(self.LEGACY, (1, "A", "x", 19.99, "EUR", "completed", "2025-03-03 10:00:00"))
        result = InternalDbImporter(allow_real_amount=True).read(path)
        self.assertEqual(result.transactions[0].amount, Decimal("19.99"))
        self.assertEqual([i.severity for i in result.issues], ["warning"])
        self.assertIn("REAL", result.issues[0].message)


class RowErrorTests(unittest.TestCase):
    def test_bad_rows_are_skipped_and_reported_but_good_rows_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps({"transactions": [
                {"id": "ok1", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 100, "currency": "EUR"}, "state": "captured"},
                {"id": "bad-amount", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 1.5, "currency": "EUR"}, "state": "captured"},
                {"id": "float-whole", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 100.0, "currency": "EUR"}, "state": "captured"},
                {"id": "bad-time", "created": "gestern", "amount": {"minor": 100, "currency": "EUR"}, "state": "captured"},
                {"id": "bad-currency", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 100, "currency": "??"}, "state": "captured"},
                "kein objekt",
                {"id": "ok2", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 250, "currency": "usd"}, "state": "PENDING"},
            ]}), encoding="utf-8")
            result = ProviderBJsonImporter().read(path)
        self.assertEqual([t.record_id for t in result.transactions], ["ok1", "ok2"])
        self.assertEqual(len(result.errors), 5)
        self.assertEqual(result.transactions[1].currency, "USD")
        self.assertIs(result.transactions[1].status, Status.PENDING)   # Status-Mapping ist case-insensitiv

    def test_internal_row_with_unknown_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "i.db"
            conn = sqlite3.connect(db)
            with conn:
                conn.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, provider TEXT, provider_ref TEXT,"
                             " amount_minor INTEGER, currency TEXT, status TEXT, created_at TEXT)")
                conn.execute("INSERT INTO transactions VALUES (1, 'C', 'x', 100, 'EUR', 'completed', '2025-03-03 10:00:00')")
                conn.execute("INSERT INTO transactions VALUES (2, 'a', 'y', 1999, 'EUR', 'weird', '2025-03-03 10:00:00')")
            conn.close()
            result = InternalDbImporter().read(db)
        self.assertEqual([t.record_id for t in result.transactions], ["2"])
        self.assertEqual(result.transactions[0].amount, Decimal("19.99"))
        self.assertEqual(sorted(i.severity for i in result.issues), ["error", "warning"])


@unittest.skipUnless(has_tzdata(), "tzdata nicht installiert")
class CsvTimezoneTests(unittest.TestCase):
    def read(self, header: str, rows: list[str], tz: str = "Europe/Berlin"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.csv"
            path.write_text(header + "".join(rows), encoding="utf-8")
            return ProviderACsvImporter(csv_timezone=tz).read(path)

    def test_local_column_uses_the_configured_zone(self):
        result = self.read("Transaktions-ID;Zeitstempel;Betrag;Waehrung;Status\n",
                           ["ATX-1;15.07.2025 12:00:00;1,00;EUR;ABGESCHLOSSEN\n"])
        self.assertEqual(result.transactions[0].timestamp.hour, 10)         # Sommerzeit: UTC+2

    def test_utc_column_ignores_the_configured_zone(self):
        result = self.read(CSV_HEADER, ["ATX-1;15.07.2025 12:00:00;1,00;EUR;ABGESCHLOSSEN\n"])
        self.assertEqual(result.transactions[0].timestamp.hour, 12)

    def test_ambiguous_local_time_is_a_row_error(self):
        result = self.read("Transaktions-ID;Zeitstempel;Betrag;Waehrung;Status\n",
                           ["ATX-1;26.10.2025 02:30:00;1,00;EUR;ABGESCHLOSSEN\n",
                            "ATX-2;26.10.2025 04:30:00;1,00;EUR;ABGESCHLOSSEN\n"])
        self.assertEqual([t.record_id for t in result.transactions], ["ATX-2"])
        self.assertIn("Zeitumstellung", result.errors[0].message)


if __name__ == "__main__":
    unittest.main()
