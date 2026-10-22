"""Kommandozeile: ``python -m txreconcile --help``.

Exit-Codes: 0 = Lauf erfolgreich, 1 = Abweichungen gefunden (nur mit ``--fail-on-discrepancy``),
2 = Quelle unlesbar oder ungültige Eingabe.
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import ReconcileConfig
from .formatting import PRIORITY_LABELS, fmt_impact
from .importers import SourceError
from .models import Priority
from .reconcile import reconcile_files
from .report import FORMATS, write_reports


def _decimal(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"keine Zahl: {text!r}") from None
    if not value.is_finite() or value < 0:
        raise argparse.ArgumentTypeError(f"muss eine endliche Zahl >= 0 sein: {text!r}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="txreconcile",
        description="Gleicht interne Buchungen (SQLite) mit den Abrechnungen von Anbieter A (CSV) und B (JSON) ab.")
    src = parser.add_argument_group("Quellen")
    src.add_argument("--db", default="data/internal.db", help="interne Datenbank (SQLite) [%(default)s]")
    src.add_argument("--provider-a", default="data/provider_a.csv", help="Abrechnung Anbieter A (CSV) [%(default)s]")
    src.add_argument("--provider-b", default="data/provider_b.json", help="Abrechnung Anbieter B (JSON) [%(default)s]")
    out = parser.add_argument_group("Ausgabe")
    out.add_argument("--out", default="reports", help="Ausgabeverzeichnis [%(default)s]")
    out.add_argument("--formats", default=",".join(FORMATS),
                     help="kommagetrennt aus: %s [%%(default)s]" % ", ".join(FORMATS))
    out.add_argument("--max-matched-rows", type=int, default=ReconcileConfig.max_matched_rows,
                     help="max. zugeordnete Zeilen im Markdown-Bericht [%(default)s]")
    out.add_argument("--quiet", action="store_true", help="keine Zusammenfassung auf der Konsole")
    out.add_argument("--fail-on-discrepancy", action="store_true", help="Exit-Code 1, wenn Abweichungen gefunden wurden")
    tune = parser.add_argument_group("Abgleich")
    tune.add_argument("--no-fuzzy", action="store_true", help="unscharfe Zuordnung deaktivieren")
    tune.add_argument("--amount-tolerance", type=_decimal, default=ReconcileConfig.amount_tolerance,
                      help="erlaubte Betragsdifferenz [%(default)s]")
    tune.add_argument("--fuzzy-window-days", type=_decimal, default=Decimal(3),
                      help="Zeitfenster der unscharfen Zuordnung in Tagen [%(default)s]")
    tune.add_argument("--high-threshold", type=_decimal, default=ReconcileConfig.high_threshold,
                      help="Priorität 'hoch' ab dieser Auswirkung (EUR) [%(default)s]")
    tune.add_argument("--medium-threshold", type=_decimal, default=ReconcileConfig.medium_threshold,
                      help="Priorität 'mittel' ab dieser Auswirkung (EUR) [%(default)s]")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")        # Umlaute auch in Windows-Konsolen/Pipes
    parser = build_parser()
    args = parser.parse_args(argv)

    formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    if not formats or set(formats) - set(FORMATS):
        parser.error(f"--formats: erlaubt sind {', '.join(FORMATS)}")
    if args.medium_threshold > args.high_threshold:
        parser.error("--medium-threshold darf nicht größer als --high-threshold sein")

    config = ReconcileConfig(
        amount_tolerance=args.amount_tolerance,
        fuzzy_enabled=not args.no_fuzzy,
        fuzzy_time_window=timedelta(days=float(args.fuzzy_window_days)),
        high_threshold=args.high_threshold,
        medium_threshold=args.medium_threshold,
        max_matched_rows=args.max_matched_rows,
    )
    try:
        result = reconcile_files(args.db, args.provider_a, args.provider_b, config)
        written = write_reports(result, args.out, formats)
    except SourceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Fehler beim Schreiben der Berichte: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        _print_summary(result, written)
    return 1 if args.fail_on_discrepancy and result.discrepancies else 0


def _print_summary(result, written: list[Path]) -> None:
    s = result.summary
    print(f"Datensätze: {s.internal_total} DB, {s.provider_total} Abrechnung  |  "
          f"zugeordnet: {s.matched} ({s.exact} exakt, {s.fuzzy} unscharf)")
    print(f"Nur DB: {s.unmatched_internal}  Nur Abrechnung: {s.unmatched_provider}  Duplikate: {s.duplicates}")
    prios = ", ".join(f"{PRIORITY_LABELS[p]} {s.by_priority.get(p, 0)}" for p in Priority)
    print(f"Abweichungen: {s.discrepancy_count} ({prios})  |  Nettoauswirkung: {fmt_impact(s.net_impact)}")
    errors = sum(len(x.errors) for x in result.sources)
    if errors or any(x.warnings for x in result.sources):
        print(f"Importprobleme: {errors} Zeilen übersprungen, {sum(len(x.warnings) for x in result.sources)} Warnungen")
    for path in written:
        print(f"  -> {path}")
