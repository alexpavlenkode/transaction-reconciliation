"""Ende-zu-Ende gegen die Ground Truth, die der Datengenerator unabhängig von der Implementierung festlegt."""
import random
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from scripts.generate_testdata import generate
from tests.helpers import DATA, canonical, config_for, diff_with_expected, load_expected
from txreconcile import reconcile, reconcile_files
from txreconcile.importers import InternalDbImporter, ProviderACsvImporter, ProviderBJsonImporter
from txreconcile.models import Certainty


def run_sample():
    expected = load_expected()
    return expected, reconcile_files(DATA / "internal.db", DATA / "provider_a.csv", DATA / "provider_b.json",
                                     config_for(expected))


class GoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected, cls.result = run_sample()

    def test_matches_discrepancies_effects_certainty_and_priorities(self):
        self.assertEqual(diff_with_expected(self.result, self.expected), [])

    def test_import_issues(self):
        errors = sum(len(s.errors) for s in self.result.sources)
        warnings = sum(len(s.warnings) for s in self.result.sources)
        self.assertEqual({"errors": errors, "warnings": warnings}, self.expected["import_issues"])

    def test_result_is_flagged_incomplete_because_rows_were_skipped(self):
        self.assertTrue(self.result.incomplete)
        self.assertEqual(len(self.result.incomplete_reasons), 2)          # Quelle A und Quelle B
        self.assertIn("ohne lesbare Referenz", " ".join(self.result.incomplete_reasons))

    def test_every_record_is_accounted_for_exactly_once(self):
        """Bilanz: jeder importierte Datensatz ist zugeordnet, unzugeordnet oder Duplikat – nie mehrfach/gar nicht."""
        m = self.result.matching
        self.assertEqual(len(m.matches) + len(m.unmatched_internal) + len(m.duplicate_internal),
                         len(self.result.internal))
        self.assertEqual(len(m.matches) + len(m.unmatched_provider) + len(m.duplicate_provider),
                         len(self.result.provider))

    def test_summary_totals_are_consistent_and_exclude_undefined_effects(self):
        s = self.result.summary
        self.assertEqual(s.discrepancy_count, len(self.result.discrepancies))
        self.assertEqual(sum(s.by_priority.values()), s.discrepancy_count)
        self.assertEqual(sum(s.by_certainty.values()), s.discrepancy_count)
        self.assertEqual(sum(k.count for k in s.by_kind.values()), s.discrepancy_count)
        for currency, total in s.net_impact.items():
            per_provider = sum(p.impact.get(currency, Decimal(0)) for p in s.providers)
            per_kind = sum(k.impact.get(currency, Decimal(0)) for k in s.by_kind.values())
            per_item = sum(d.impact.get(currency, Decimal(0)) for d in self.result.discrepancies)
            self.assertEqual(total, per_provider)
            self.assertEqual(total, per_kind)
            self.assertEqual(total, per_item)
        # nicht bestimmbare Befunde tragen nichts zur Summe bei, werden aber gezählt
        undefined = [d for d in self.result.discrepancies if d.certainty is Certainty.UNDEFINED]
        self.assertEqual(s.undefined_count, len(undefined))
        self.assertTrue(all(d.impact == {} for d in undefined))
        self.assertEqual(s.net_impact, {"EUR": Decimal("-16583.91")})     # von Hand nachgerechnet, siehe data/README.md

    def test_committed_testdata_matches_generator(self):
        """Die eingecheckten Dateien entsprechen dem Generator (Seed 2025) – Drift fällt sofort auf."""
        with tempfile.TemporaryDirectory() as tmp:
            generate(Path(tmp))
            for name in ("provider_a.csv", "provider_b.json", "expected.json"):
                self.assertEqual((Path(tmp) / name).read_bytes(), (DATA / name).read_bytes(), name)


class PermutationTests(unittest.TestCase):
    """Die Reihenfolge der Eingabezeilen darf das Ergebnis nicht ändern."""

    def test_shuffled_input_gives_identical_result(self):
        expected = load_expected()
        config = config_for(expected)
        internal = InternalDbImporter().read(DATA / "internal.db")
        provider_a = ProviderACsvImporter().read(DATA / "provider_a.csv")
        provider_b = ProviderBJsonImporter().read(DATA / "provider_b.json")
        baseline = canonical(reconcile(internal, [provider_a, provider_b], config))
        for seed in range(6):
            rng = random.Random(seed)

            def shuffled(source):
                txs, issues = source.transactions[:], source.issues[:]
                rng.shuffle(txs)
                rng.shuffle(issues)
                return replace(source, transactions=txs, issues=issues)

            sources = [shuffled(s) for s in (internal, provider_a, provider_b)]
            if seed % 2:
                sources[1], sources[2] = sources[2], sources[1]          # auch die Reihenfolge der Anbieterquellen
            self.assertEqual(canonical(reconcile(sources[0], sources[1:], config)), baseline, f"seed={seed}")


class BulkConsistencyTests(unittest.TestCase):
    def test_bulk_dataset_recovers_all_injected_anomalies(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate(out, seed=7, curated=False, bulk=1500)
            expected = load_expected(out / "expected.json")
            result = reconcile_files(out / "internal.db", out / "provider_a.csv", out / "provider_b.json",
                                     config_for(expected))
            self.assertEqual(diff_with_expected(result, expected, check_priority=False), [])


if __name__ == "__main__":
    unittest.main()
