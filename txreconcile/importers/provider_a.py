"""Importer für Zahlungsdienstleister A (CSV, ``;``-getrennt, deutsches Format).

Beispielzeile::

    Transaktions-ID;Zeitstempel (UTC);Betrag;Waehrung;Status
    ATX-48213907;03.03.2025 10:16:02;1.234,56;EUR;ABGESCHLOSSEN

Zeitstempel: Die Spalte ``Zeitstempel (UTC)`` ist UTC. Liefert ein Export stattdessen eine Spalte
``Zeitstempel`` (Ortszeit ohne Offset), gilt die Zone ``csv_timezone`` (z. B. ``Europe/Berlin``);
Uhrzeiten, die durch die Zeitumstellung mehrdeutig sind oder nicht existieren, werden als Fehler gemeldet.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..models import Status, Transaction
from ..normalize import (ID_RULES, IdRule, get_timezone, normalize_currency, normalize_reference,
                         parse_german_amount, parse_german_timestamp, quantize_money)
from .base import ImportIssue, ImportResult, Importer, SourceError, map_status

COL_ID, COL_AMOUNT, COL_CURRENCY, COL_STATUS = "Transaktions-ID", "Betrag", "Waehrung", "Status"
COL_TIME_UTC, COL_TIME_LOCAL = "Zeitstempel (UTC)", "Zeitstempel"
REQUIRED_COLUMNS = [COL_ID, COL_AMOUNT, COL_CURRENCY, COL_STATUS]

STATUS_MAP = {
    "abgeschlossen": Status.COMPLETED,
    "ausstehend": Status.PENDING,
    "fehlgeschlagen": Status.FAILED,
    "erstattet": Status.REFUNDED,
}


class ProviderACsvImporter(Importer):
    source = "provider_a"
    provider = "A"

    def __init__(self, csv_timezone: str = "UTC", id_rule: IdRule | None = None) -> None:
        self.csv_timezone = csv_timezone
        self.id_rule = id_rule or ID_RULES["A"]

    def read(self, path: str | Path) -> ImportResult:
        file = self.check_file(path)
        result = ImportResult(source=self.source, path=file.as_posix())
        try:
            zone = get_timezone(self.csv_timezone)
        except ValueError as exc:
            raise SourceError(str(exc)) from exc
        try:
            # utf-8-sig: Excel-Exporte beginnen oft mit einem BOM, der sonst im ersten Spaltennamen landet.
            with file.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                fields = reader.fieldnames or []
                missing = [c for c in REQUIRED_COLUMNS if c not in fields]
                time_col = COL_TIME_UTC if COL_TIME_UTC in fields else COL_TIME_LOCAL if COL_TIME_LOCAL in fields else None
                if time_col is None:
                    missing.append(f"{COL_TIME_UTC} oder {COL_TIME_LOCAL}")
                if missing:
                    raise SourceError(f"{file}: Spalten fehlen: {', '.join(missing)}")
                # Eine UTC-Spalte ist UTC, egal was als Ortszeit-Zone eingestellt ist.
                time_zone = get_timezone("UTC") if time_col == COL_TIME_UTC else zone
                for row in reader:
                    if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
                        continue                     # Leerzeile (z. B. am Dateiende)
                    result.rows_read += 1
                    self._read_row(row, time_col, time_zone, f"Zeile {reader.line_num}", result)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise SourceError(f"{file} nicht lesbar: {exc}") from exc
        return result

    def _read_row(self, row: dict, time_col: str, zone, location: str, result: ImportResult) -> None:
        ref = (row.get(COL_ID) or "").strip() or None
        key = normalize_reference(ref, self.id_rule)
        try:
            if ref is None:
                raise ValueError("Transaktions-ID fehlt")
            missing = [c for c in (*REQUIRED_COLUMNS, time_col) if row.get(c) is None]
            if missing:
                raise ValueError(f"Spalten fehlen in der Zeile: {', '.join(missing)}")
            currency = normalize_currency(row[COL_CURRENCY])
            status, warning = map_status(row[COL_STATUS], STATUS_MAP)
            tx = Transaction(
                source=self.source, provider="A", record_id=ref, reference=ref,
                amount=quantize_money(parse_german_amount(row[COL_AMOUNT]), currency),
                currency=currency, status=status,
                timestamp=parse_german_timestamp(row[time_col], zone), raw_status=row[COL_STATUS].strip(),
                key=key,
            )
        except ValueError as exc:
            result.issues.append(ImportIssue(self.source, location, "error", f"Zeile übersprungen: {exc}",
                                             ref, "A", key))
            return
        if warning:
            result.issues.append(ImportIssue(self.source, location, "warning", warning, ref, "A", key))
        result.transactions.append(tx)
