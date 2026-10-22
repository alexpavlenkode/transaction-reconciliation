import contextlib
import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from decimal import Decimal

from tests.helpers import DATA, T0
from txreconcile import ReconcileConfig, reconcile, reconcile_files
from txreconcile.cli import main
from txreconcile.importers import ImportResult
from txreconcile.models import Status, Transaction
from txreconcile.report import write_reports
from txreconcile.report.markdown import render_markdown
from txreconcile.report.html import render_html


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = reconcile_files(DATA / "internal.db", DATA / "provider_a.csv", DATA / "provider_b.json")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.files = write_reports(cls.result, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_files_are_written(self):
        self.assertEqual({f.name for f in self.files},
                         {"report.md", "report.html", "report.json", "discrepancies.csv", "matched.csv"})

    def test_markdown_has_all_sections_and_both_transaction_groups(self):
        text = render_markdown(self.result)
        for heading in ("## 1. Zusammenfassung", "## 2. Priorisierte Abweichungen", "## 3. Nicht zugeordnete",
                        "## 4. Zugeordnete Transaktionen", "## 5. Importprobleme", "## 6. Methodik"):
            self.assertIn(heading, text)
        self.assertIn("D-001", text)
        self.assertIn("✅ in Ordnung", text)

    def test_markdown_truncates_matched_rows_but_json_keeps_all(self):
        result = reconcile_files(DATA / "internal.db", DATA / "provider_a.csv", DATA / "provider_b.json",
                                 ReconcileConfig(max_matched_rows=5))
        self.assertIn("weitere Zeilen", render_markdown(result))
        data = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["matched"]), self.result.summary.matched)

    def test_json_structure_and_decimal_strings(self):
        data = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["discrepancies"], len(data["discrepancies"]))
        self.assertEqual(data["discrepancies"][0]["id"], "D-001")
        self.assertIsInstance(data["discrepancies"][0]["impact"]["EUR"], str)   # keine float-Rundung im Export

    def test_discrepancy_csv_is_complete(self):
        with (self.out / "discrepancies.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), len(self.result.discrepancies))
        self.assertEqual(rows[0]["priority"], "HIGH")
        self.assertTrue(all(r["action"] for r in rows))

    def test_html_embeds_valid_json_and_is_self_contained(self):
        html = render_html(self.result)
        payload = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(payload)["summary"]["matched"], self.result.summary.matched)
        self.assertNotRegex(html, r'(src|href)="https?://')      # keine externen Abhängigkeiten

    def test_html_payload_cannot_break_out_of_script_tag(self):
        evil = Transaction(source="internal", provider="A", record_id="1", reference="</script><b>x",
                           amount=Decimal("5"), currency="EUR", status=Status.COMPLETED, timestamp=T0,
                           note="</script><script>alert(1)</script>")
        result = reconcile(ImportResult("internal", "i.db", [evil]), [ImportResult("provider_a", "a.csv", [])])
        html = render_html(result)
        self.assertEqual(html.count("</script>"), 2)                 # genau die zwei eigenen Script-Blöcke
        self.assertIn("alert(1)", html)                              # Inhalt ist da, nur eben maskiert

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            write_reports(self.result, self.out, ("pdf",))


class CliTests(unittest.TestCase):
    def run_cli(self, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--db", str(DATA / "internal.db"), "--provider-a", str(DATA / "provider_a.csv"),
                         "--provider-b", str(DATA / "provider_b.json"), "--out", tmp, "--quiet", *extra])
            return code, sorted(p.name for p in Path(tmp).iterdir())

    def test_success_writes_reports(self):
        code, files = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("report.md", files)

    def test_formats_option(self):
        code, files = self.run_cli("--formats", "json")
        self.assertEqual((code, files), (0, ["report.json"]))

    def test_fail_on_discrepancy(self):
        self.assertEqual(self.run_cli("--fail-on-discrepancy")[0], 1)

    def test_missing_source_returns_exit_code_2(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["--db", str(Path(tmp) / "nope.db"), "--out", tmp, "--quiet"])
        self.assertEqual(code, 2)
        self.assertIn("Datei nicht gefunden", err.getvalue())

    def test_invalid_arguments_exit_with_argparse_error(self):
        for args in (["--formats", "pdf"], ["--amount-tolerance", "abc"], ["--high-threshold", "10", "--medium-threshold", "20"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as ctx:
                main(args)
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
