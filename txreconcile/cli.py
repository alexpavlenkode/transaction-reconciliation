"""Kommandozeile: ``python -m txreconcile --as-of 2025-04-01``.

Exit-Codes:

* 0 – Lauf erfolgreich
* 1 – Abweichungen gefunden (nur mit ``--fail-on-discrepancy``)
* 2 – Quelle unlesbar oder ungültige Eingabe (kein Abgleich: ein Vergleich mit einer unvollständig
      gelesenen Quelle würde falsche Befunde erzeugen)
* 3 – Ergebnis unvollständig, weil Zeilen übersprungen wurden (nur mit ``--fail-on-incomplete``);
      hat Vorrang vor 1
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import ReconcileConfig
from .formatting import PRIORITY_LABELS, fmt_amounts, fmt_impact
from .importers import SourceError
from .models import Priority
from .normalize import parse_iso_timestamp
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


def _as_of(text: str) -> datetime:
    try:
        return parse_iso_timestamp(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"kein gültiger Zeitpunkt: {text!r} (z. B. 2025-04-01 oder 2025-04-01T12:00:00+02:00)") from None


def _currency_threshold(text: str) -> tuple[str, tuple[Decimal, Decimal]]:
    """``JPY=75000:7500`` -> ``('JPY', (75000, 7500))``"""
    try:
        currency, limits = text.split("=", 1)
        high, medium = (_decimal(part) for part in limits.split(":", 1))
        if len(currency.strip()) != 3 or medium > high:
            raise ValueError
        return currency.strip().upper(), (high, medium)
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError(
            f"erwartet WÄHRUNG=HOCH:MITTEL mit MITTEL <= HOCH, z. B. JPY=75000:7500 (erhalten: {text!r})") from None


class _GermanFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "Aufruf: " if prefix is None else prefix)


_ARGPARSE_TEXTE = (
    ("the following arguments are required:", "folgende Argumente fehlen:"),
    ("unrecognized arguments:", "unbekannte Argumente:"),
    ("expected one argument", "erwartet einen Wert"),
    ("invalid choice:", "ungültige Auswahl:"),
    ("ambiguous option:", "mehrdeutige Option:"),
    ("not allowed with argument", "nicht kombinierbar mit Argument"),
)


class _GermanParser(argparse.ArgumentParser):
    """``argparse`` mit deutschen Standardtexten (Aufruf, Fehlermeldungen, Hilfe)."""

    def error(self, message: str):
        for english, german in _ARGPARSE_TEXTE:
            message = message.replace(english, german)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: Fehler: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _GermanParser(
        prog="txreconcile", add_help=False, formatter_class=_GermanFormatter,
        description="Gleicht interne Buchungen (SQLite) mit den Abrechnungen von Anbieter A (CSV) und B (JSON) ab.")
    parser.add_argument_group("Allgemein").add_argument(
        "-h", "--help", action="help", help="diese Hilfe anzeigen und beenden")
    src = parser.add_argument_group("Quellen")
    src.add_argument("--db", default="data/internal.db", help="interne Datenbank (SQLite) [%(default)s]")
    src.add_argument("--provider-a", default="data/provider_a.csv", help="Abrechnung Anbieter A (CSV) [%(default)s]")
    src.add_argument("--provider-b", default="data/provider_b.json", help="Abrechnung Anbieter B (JSON) [%(default)s]")
    src.add_argument("--allow-real-amount", action="store_true",
                     help="Altbestand: Beträge aus einer REAL-Spalte 'amount' lesen (ungenau, wird gerundet und "
                          "gewarnt). Standard ist die Spalte 'amount_minor' (INTEGER)")
    src.add_argument("--csv-timezone", default="UTC",
                     help="Zeitzone für CSV-Zeiten ohne Offset in einer Spalte 'Zeitstempel' [%(default)s]")
    time = parser.add_argument_group("Stichtag und Fristen")
    time.add_argument("--as-of", type=_as_of, required=True, metavar="ZEITPUNKT",
                      help="Stichtag der Auswertung (Pflicht, macht den Lauf reproduzierbar); "
                           "die Eingabedateien müssen den Stand zu diesem Zeitpunkt zeigen")
    time.add_argument("--settlement-lag-days", type=_decimal, default=Decimal(3),
                      help="zulässige Verzögerung bis zur Abrechnung in Tagen [%(default)s]")
    out = parser.add_argument_group("Ausgabe")
    out.add_argument("--out", default="reports", help="Ausgabeverzeichnis [%(default)s]")
    out.add_argument("--formats", default=",".join(FORMATS),
                     help="kommagetrennt aus: %s [%%(default)s]" % ", ".join(FORMATS))
    out.add_argument("--max-matched-rows", type=int, default=ReconcileConfig.max_matched_rows,
                     help="max. zugeordnete Zeilen im Markdown-Bericht [%(default)s]")
    out.add_argument("--quiet", action="store_true", help="keine Zusammenfassung auf der Konsole")
    out.add_argument("--fail-on-discrepancy", action="store_true", help="Exit-Code 1, wenn Abweichungen gefunden wurden")
    out.add_argument("--fail-on-incomplete", action="store_true",
                     help="Exit-Code 3, wenn Zeilen übersprungen wurden (Ergebnis unvollständig)")
    tune = parser.add_argument_group("Abgleich")
    tune.add_argument("--no-fuzzy", action="store_true", help="unscharfe Zuordnung deaktivieren")
    tune.add_argument("--amount-tolerance", type=_decimal, default=ReconcileConfig.amount_tolerance,
                      help="erlaubte Betragsdifferenz [%(default)s]")
    tune.add_argument("--fuzzy-window-days", type=_decimal, default=Decimal(3),
                      help="Zeitfenster der unscharfen Zuordnung in Tagen [%(default)s]")
    tune.add_argument("--high-threshold", type=_decimal, default=ReconcileConfig.high_threshold,
                      help="Schwere 'hoch' ab diesem Betrag, je Währung ohne eigene Schwelle [%(default)s]")
    tune.add_argument("--medium-threshold", type=_decimal, default=ReconcileConfig.medium_threshold,
                      help="Schwere 'mittel' ab diesem Betrag, je Währung ohne eigene Schwelle [%(default)s]")
    tune.add_argument("--currency-threshold", type=_currency_threshold, action="append", default=[],
                      metavar="WÄHRUNG=HOCH:MITTEL",
                      help="eigene Schwellen für eine Währung, wiederholbar (Standard: JPY=75000:7500)")
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

    defaults = ReconcileConfig()
    currency_thresholds = {**defaults.currency_thresholds, **dict(args.currency_threshold)}
    config = ReconcileConfig(
        as_of=args.as_of,
        settlement_lag=timedelta(days=float(args.settlement_lag_days)),
        amount_tolerance=args.amount_tolerance,
        fuzzy_enabled=not args.no_fuzzy,
        fuzzy_time_window=timedelta(days=float(args.fuzzy_window_days)),
        high_threshold=args.high_threshold,
        medium_threshold=args.medium_threshold,
        currency_thresholds=currency_thresholds,
        max_matched_rows=args.max_matched_rows,
    )
    try:
        result = reconcile_files(args.db, args.provider_a, args.provider_b, config,
                                 allow_real_amount=args.allow_real_amount, csv_timezone=args.csv_timezone)
        written = write_reports(result, args.out, formats)
    except SourceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Fehler beim Schreiben der Berichte: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        _print_summary(result, written)
    if args.fail_on_incomplete and result.incomplete:
        return 3
    return 1 if args.fail_on_discrepancy and result.discrepancies else 0


def _print_summary(result, written: list[Path]) -> None:
    s = result.summary
    if result.incomplete:
        print("ACHTUNG: Ergebnis unvollständig – " + "; ".join(result.incomplete_reasons))
    print(f"Datensätze: {s.internal_total} DB, {s.provider_total} Abrechnung  |  "
          f"zugeordnet: {s.matched} ({s.exact} exakt, {s.fuzzy} unscharf)")
    print(f"Nur DB: {s.unmatched_internal}  Nur Abrechnung: {s.unmatched_provider}  Duplikate: {s.duplicates}")
    prios = ", ".join(f"{PRIORITY_LABELS[p]} {s.by_priority.get(p, 0)}" for p in Priority)
    print(f"Abweichungen: {s.discrepancy_count} ({prios})  |  berechnete Nettoauswirkung: {fmt_impact(s.net_impact)}")
    if s.undefined_count:
        print(f"Davon {s.undefined_count} ohne bestimmbare Auswirkung (betroffen: {fmt_amounts(s.undefined_affected)}), "
              f"{s.preliminary_count} vorläufig")
    errors = sum(len(x.errors) for x in result.sources)
    warnings = sum(len(x.warnings) for x in result.sources)
    if errors or warnings:
        print(f"Importprobleme: {errors} Zeilen übersprungen, {warnings} Warnungen")
    for path in written:
        print(f"  -> {path}")
