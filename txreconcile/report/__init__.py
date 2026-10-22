"""Berichtsausgaben: Markdown, HTML-Dashboard, JSON, CSV."""
from __future__ import annotations

from pathlib import Path

from ..reconcile import ReconciliationResult
from .exports import write_discrepancies_csv, write_json, write_matched_csv
from .html import render_html
from .markdown import render_markdown

FORMATS = ("md", "html", "json", "csv")


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:      # überall LF, reproduzierbare Dateien
        handle.write(text)


def write_reports(result: ReconciliationResult, out_dir: str | Path, formats: tuple[str, ...] = FORMATS) -> list[Path]:
    """Schreibt die gewünschten Formate nach ``out_dir`` und gibt die erzeugten Dateien zurück."""
    unknown = set(formats) - set(FORMATS)
    if unknown:
        raise ValueError(f"unbekannte Formate: {', '.join(sorted(unknown))} (erlaubt: {', '.join(FORMATS)})")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if "md" in formats:
        _write_text(out / "report.md", render_markdown(result))
        written.append(out / "report.md")
    if "html" in formats:
        _write_text(out / "report.html", render_html(result))
        written.append(out / "report.html")
    if "json" in formats:
        write_json(result, out / "report.json")
        written.append(out / "report.json")
    if "csv" in formats:
        write_discrepancies_csv(result, out / "discrepancies.csv")
        write_matched_csv(result, out / "matched.csv")
        written += [out / "discrepancies.csv", out / "matched.csv"]
    return written
