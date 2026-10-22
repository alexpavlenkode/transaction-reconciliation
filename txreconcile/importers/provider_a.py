"""Importer für Zahlungsdienstleister A (CSV, ``;``-getrennt, deutsches Format).

Beispielzeile::

    Transaktions-ID;Zeitstempel (UTC);Betrag;Waehrung;Status
    ATX-48213907;03.03.2025 10:16:02;1.234,56;EUR;ABGESCHLOSSEN
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..models import Status, Transaction
from ..normalize import normalize_currency, parse_german_amount, parse_german_timestamp, quantize_money
from .base import ImportIssue, ImportResult, Importer, SourceError, map_status

COL_ID, COL_TIME, COL_AMOUNT, COL_CURRENCY, COL_STATUS = (
    "Transaktions-ID", "Zeitstempel (UTC)", "Betrag", "Waehrung", "Status")
REQUIRED_COLUMNS = [COL_ID, COL_TIME, COL_AMOUNT, COL_CURRENCY, COL_STATUS]

STATUS_MAP = {
    "abgeschlossen": Status.COMPLETED,
    "ausstehend": Status.PENDING,
    "fehlgeschlagen": Status.FAILED,
    "erstattet": Status.REFUNDED,
}


class ProviderACsvImporter(Importer):
    source = "provider_a"
    provider = "A"

    def read(self, path: str | Path) -> ImportResult:
        file = self.check_file(path)
        result = ImportResult(source=self.source, path=file.as_posix())
        try:
            # utf-8-sig: Excel-Exporte beginnen oft mit einem BOM, der sonst im ersten Spaltennamen landet.
            with file.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
                if missing:
                    raise SourceError(f"{file}: Spalten fehlen: {', '.join(missing)}")
                for row in reader:
                    if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
                        continue                     # Leerzeile (z. B. am Dateiende)
                    result.rows_read += 1
                    self._read_row(row, f"Zeile {reader.line_num}", result)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise SourceError(f"{file} nicht lesbar: {exc}") from exc
        return result

    def _read_row(self, row: dict, location: str, result: ImportResult) -> None:
        ref = (row.get(COL_ID) or "").strip() or None
        try:
            if ref is None:
                raise ValueError("Transaktions-ID fehlt")
            missing = [c for c in REQUIRED_COLUMNS if row.get(c) is None]
            if missing:
                raise ValueError(f"Spalten fehlen in der Zeile: {', '.join(missing)}")
            currency = normalize_currency(row[COL_CURRENCY])
            status, warning = map_status(row[COL_STATUS], STATUS_MAP)
            tx = Transaction(
                source=self.source, provider="A", record_id=ref, reference=ref,
                amount=quantize_money(parse_german_amount(row[COL_AMOUNT]), currency),
                currency=currency, status=status,
                timestamp=parse_german_timestamp(row[COL_TIME]), raw_status=row[COL_STATUS].strip(),
            )
        except ValueError as exc:
            result.issues.append(ImportIssue(self.source, location, "error", f"Zeile übersprungen: {exc}", ref))
            return
        if warning:
            result.issues.append(ImportIssue(self.source, location, "warning", warning, ref))
        result.transactions.append(tx)
