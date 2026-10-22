import json
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests.helpers import DATA
from txreconcile.importers import (InternalDbImporter, ProviderACsvImporter, ProviderBJsonImporter, SourceError)
from txreconcile.models import Status


class SampleDataImportTests(unittest.TestCase):
    def test_internal_db(self):
        result = InternalDbImporter().read(DATA / "internal.db")
        self.assertEqual(len(result.transactions), result.rows_read)
        self.assertEqual(result.issues, [])
        first = result.transactions[0]
        self.assertEqual(first.source, "internal")
        self.assertIsInstance(first.amount, Decimal)
        self.assertIsNotNone(first.timestamp.tzinfo)

    def test_provider_a_csv_parses_german_format_and_reports_bad_row(self):
        result = ProviderACsvImporter().read(DATA / "provider_a.csv")
        self.assertEqual(result.rows_read, 29)             # Leerzeile am Ende zählt nicht
        self.assertEqual(len(result.transactions), 28)
        self.assertEqual([(i.severity, i.location.startswith("Zeile")) for i in result.issues], [("error", True)])
        self.assertIn("n/a", result.issues[0].message)
        self.assertIsNotNone(result.issues[0].reference)   # Verknüpfung mit der Gegenseite bleibt erhalten

    def test_provider_b_json_minor_units_and_issues(self):
        result = ProviderBJsonImporter().read(DATA / "provider_b.json")
        self.assertEqual(result.rows_read, 17)
        self.assertEqual(len(result.transactions), 16)     # ein Eintrag ohne id
        severities = sorted(i.severity for i in result.issues)
        self.assertEqual(severities, ["error", "warning"])
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
        partial = self.tmp / "partial.db"
        with sqlite3.connect(partial) as conn:
            conn.execute("CREATE TABLE transactions (id INTEGER)")
        conn.close()
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


class RowErrorTests(unittest.TestCase):
    def test_bad_rows_are_skipped_and_reported_but_good_rows_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps({"transactions": [
                {"id": "ok1", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 100, "currency": "EUR"}, "state": "captured"},
                {"id": "bad-amount", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 1.5, "currency": "EUR"}, "state": "captured"},
                {"id": "bad-time", "created": "gestern", "amount": {"minor": 100, "currency": "EUR"}, "state": "captured"},
                {"id": "bad-currency", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 100, "currency": "??"}, "state": "captured"},
                "kein objekt",
                {"id": "ok2", "created": "2025-03-03T10:00:00Z", "amount": {"minor": 250, "currency": "usd"}, "state": "PENDING"},
            ]}), encoding="utf-8")
            result = ProviderBJsonImporter().read(path)
        self.assertEqual([t.record_id for t in result.transactions], ["ok1", "ok2"])
        self.assertEqual(len(result.errors), 4)
        self.assertEqual(result.transactions[1].currency, "USD")
        self.assertIs(result.transactions[1].status, Status.PENDING)   # Status-Mapping ist case-insensitiv

    def test_internal_row_with_unknown_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "i.db"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, provider TEXT, provider_ref TEXT,"
                             " amount REAL, currency TEXT, status TEXT, created_at TEXT)")
                conn.execute("INSERT INTO transactions VALUES (1, 'C', 'x', 1.0, 'EUR', 'completed', '2025-03-03 10:00:00')")
                conn.execute("INSERT INTO transactions VALUES (2, 'a', 'y', 19.99, 'EUR', 'weird', '2025-03-03 10:00:00')")
            conn.close()
            result = InternalDbImporter().read(db)
        self.assertEqual([t.record_id for t in result.transactions], ["2"])
        self.assertEqual(result.transactions[0].amount, Decimal("19.99"))
        self.assertEqual(sorted(i.severity for i in result.issues), ["error", "warning"])


if __name__ == "__main__":
    unittest.main()
