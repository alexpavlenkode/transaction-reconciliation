"""Ende-zu-Ende gegen die Ground Truth, die der Datengenerator unabhängig von der Implementierung festlegt."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.generate_testdata import generate
from tests.helpers import DATA, diff_with_expected, load_expected
from txreconcile import reconcile_files


class GoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = load_expected()
        cls.result = reconcile_files(DATA / "internal.db", DATA / "provider_a.csv", DATA / "provider_b.json")

    def test_matches_discrepancies_impacts_and_priorities(self):
        self.assertEqual(diff_with_expected(self.result, self.expected), [])

    def test_import_issues(self):
        errors = sum(len(s.errors) for s in self.result.sources)
        warnings = sum(len(s.warnings) for s in self.result.sources)
        self.assertEqual({"errors": errors, "warnings": warnings}, self.expected["import_issues"])

    def test_every_record_is_accounted_for_exactly_once(self):
        """Bilanz: jeder importierte Datensatz ist zugeordnet, unzugeordnet oder Duplikat – nie mehrfach/gar nicht."""
        m = self.result.matching
        self.assertEqual(len(m.matches) + len(m.unmatched_internal) + len(m.duplicate_internal),
                         len(self.result.internal))
        self.assertEqual(len(m.matches) + len(m.unmatched_provider) + len(m.duplicate_provider),
                         len(self.result.provider))

    def test_summary_totals_are_consistent(self):
        s = self.result.summary
        self.assertEqual(s.discrepancy_count, len(self.result.discrepancies))
        self.assertEqual(sum(s.by_priority.values()), s.discrepancy_count)
        self.assertEqual(sum(k.count for k in s.by_kind.values()), s.discrepancy_count)
        for currency, total in s.net_impact.items():
            per_provider = sum(p.impact.get(currency, Decimal(0)) for p in s.providers)
            per_kind = sum(k.impact.get(currency, Decimal(0)) for k in s.by_kind.values())
            self.assertEqual(total, per_provider)
            self.assertEqual(total, per_kind)

    def test_committed_testdata_matches_generator(self):
        """Die eingecheckten Dateien entsprechen dem Generator (Seed 2025) – Drift fällt sofort auf."""
        with tempfile.TemporaryDirectory() as tmp:
            generate(Path(tmp))
            for name in ("provider_a.csv", "provider_b.json", "expected.json"):
                self.assertEqual((Path(tmp) / name).read_bytes(), (DATA / name).read_bytes(), name)


class BulkConsistencyTests(unittest.TestCase):
    def test_bulk_dataset_recovers_all_injected_anomalies(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate(out, seed=7, curated=False, bulk=1500)
            result = reconcile_files(out / "internal.db", out / "provider_a.csv", out / "provider_b.json")
            self.assertEqual(diff_with_expected(result, load_expected(out / "expected.json"), check_priority=False), [])


if __name__ == "__main__":
    unittest.main()
