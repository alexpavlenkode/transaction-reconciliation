import contextlib
import csv
import io
import json
import re
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests.helpers import DATA, T0, config_for, load_expected
from txreconcile import ReconcileConfig, reconcile, reconcile_files
from txreconcile.cli import main
from txreconcile.importers import ImportResult
from txreconcile.models import Status, Transaction
from txreconcile.report import write_reports
from txreconcile.report.html import render_html
from txreconcile.report.markdown import render_markdown

SOURCES = ["--db", str(DATA / "internal.db"), "--provider-a", str(DATA / "provider_a.csv"),
           "--provider-b", str(DATA / "provider_b.json")]


def sample(config=None):
    return reconcile_files(DATA / "internal.db", DATA / "provider_a.csv", DATA / "provider_b.json",
                           config or config_for(load_expected()))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = sample()
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

    def test_markdown_shows_incomplete_banner_and_separates_undefined_effects(self):
        text = render_markdown(self.result)
        self.assertIn("Ergebnis unvollständig", text)
        self.assertIn("nicht bestimmbar (betroffen:", text)
        self.assertIn("sind **nicht** in diesen Summen enthalten", text)
        self.assertIn("keinen nachgewiesenen Verlust", text)

    def test_complete_result_has_no_banner(self):
        clean = reconcile(ImportResult("internal", "i.db", []), [ImportResult("provider_a", "a.csv", [])])
        self.assertFalse(clean.incomplete)
        self.assertNotIn("unvollständig", render_markdown(clean).split("## 1.")[0])

    def test_report_is_byte_reproducible(self):
        again = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in again.iterdir()] and again.rmdir())
        write_reports(sample(), again)
        for name in ("report.md", "report.html", "report.json", "discrepancies.csv", "matched.csv"):
            self.assertEqual((again / name).read_bytes(), (self.out / name).read_bytes(), name)

    def test_markdown_truncates_matched_rows_but_json_keeps_all(self):
        expected = load_expected()
        config = ReconcileConfig(as_of=config_for(expected).as_of, max_matched_rows=5)
        self.assertIn("weitere Zeilen", render_markdown(sample(config)))
        data = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["matched"]), self.result.summary.matched)

    def test_json_structure_and_decimal_strings(self):
        data = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["discrepancies"], len(data["discrepancies"]))
        self.assertEqual(data["discrepancies"][0]["id"], "D-001")
        self.assertTrue(data["incomplete"])
        self.assertEqual(data["as_of"], "2025-04-01T00:00:00+00:00")
        eur = [d for d in data["discrepancies"] if d["effect_defined"] and d["impact"].get("EUR")]
        self.assertIsInstance(eur[0]["impact"]["EUR"], str)                # keine float-Rundung im Export
        undefined = [d for d in data["discrepancies"] if not d["effect_defined"]]
        self.assertTrue(undefined)
        self.assertTrue(all(d["impact"] == {} and d["affected"] for d in undefined))

    def test_discrepancy_csv_is_complete_and_marks_certainty(self):
        with (self.out / "discrepancies.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), len(self.result.discrepancies))
        self.assertEqual(rows[0]["priority"], "HIGH")
        self.assertTrue(all(r["action"] for r in rows))
        undefined = [r for r in rows if r["certainty"] == "UNDEFINED"]
        self.assertTrue(undefined and all(r["impact"] == "" and r["affected"] for r in undefined))

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
    def run_cli(self, *extra, sources=True):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            code = main([*(SOURCES if sources else []), "--out", tmp, "--quiet", *extra])
            return code, sorted(p.name for p in Path(tmp).iterdir())

    def test_success_writes_reports(self):
        code, files = self.run_cli("--as-of", "2025-04-01")
        self.assertEqual(code, 0)
        self.assertIn("report.md", files)

    def test_as_of_is_mandatory(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as ctx:
            main([*SOURCES, "--quiet"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--as-of", err.getvalue())

    def test_as_of_changes_the_result_not_the_system_clock(self):
        def count(as_of):
            with tempfile.TemporaryDirectory() as tmp:
                main([*SOURCES, "--out", tmp, "--quiet", "--formats", "json", "--as-of", as_of])
                data = json.loads((Path(tmp) / "report.json").read_text(encoding="utf-8"))
                return sum(1 for d in data["discrepancies"] if "NOT_YET_DUE" in d["kinds"])
        self.assertEqual(count("2025-04-01"), 1)       # eine Buchung vom 31.03. liegt noch in der Frist
        self.assertEqual(count("2025-04-20"), 0)       # später sind alle fällig
        self.assertEqual(count("2025-04-01"), count("2025-04-01"))

    def test_formats_option(self):
        code, files = self.run_cli("--as-of", "2025-04-01", "--formats", "json")
        self.assertEqual((code, files), (0, ["report.json"]))

    def test_exit_codes_for_discrepancies_and_incomplete_results(self):
        self.assertEqual(self.run_cli("--as-of", "2025-04-01", "--fail-on-discrepancy")[0], 1)
        self.assertEqual(self.run_cli("--as-of", "2025-04-01", "--fail-on-incomplete")[0], 3)
        # unvollständig hat Vorrang vor "Abweichungen gefunden"
        self.assertEqual(self.run_cli("--as-of", "2025-04-01", "--fail-on-incomplete", "--fail-on-discrepancy")[0], 3)
        self.assertEqual(self.run_cli("--as-of", "2025-04-01")[0], 0)

    def test_currency_threshold_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            main([*SOURCES, "--out", tmp, "--quiet", "--formats", "json", "--as-of", "2025-04-01",
                  "--currency-threshold", "USD=100:10"])
            data = json.loads((Path(tmp) / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(data["config"]["currency_thresholds"]["USD"], {"high": "100", "medium": "10"})
        self.assertIn("JPY", data["config"]["currency_thresholds"])      # Standard bleibt erhalten

    def test_missing_source_returns_exit_code_2(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["--db", str(Path(tmp) / "nope.db"), "--out", tmp, "--quiet", "--as-of", "2025-04-01"])
        self.assertEqual(code, 2)
        self.assertIn("Datei nicht gefunden", err.getvalue())

    def test_real_amount_column_is_refused_without_the_legacy_flag(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            db = Path(tmp) / "old.db"
            conn = sqlite3.connect(db)
            with conn:
                conn.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, provider TEXT, provider_ref TEXT,"
                             " amount REAL, currency TEXT, status TEXT, created_at TEXT)")
            conn.close()
            code = main([*SOURCES[2:], "--db", str(db), "--out", tmp, "--quiet", "--as-of", "2025-04-01"])
        self.assertEqual(code, 2)
        self.assertIn("allow-real-amount", err.getvalue())

    def test_invalid_arguments_exit_with_argparse_error(self):
        for args in (["--formats", "pdf"], ["--amount-tolerance", "abc"], ["--high-threshold", "10", "--medium-threshold", "20"],
                     ["--as-of", "gestern"], ["--currency-threshold", "JPY=1"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as ctx:
                main([*SOURCES, "--as-of", "2025-04-01", *args])
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
