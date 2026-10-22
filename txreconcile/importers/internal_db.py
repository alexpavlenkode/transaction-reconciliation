"""Importer für die interne Datenbank (SQLite, Tabelle ``transactions``)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Status, Transaction
from ..normalize import normalize_currency, parse_decimal, parse_iso_timestamp, quantize_money
from .base import ImportIssue, ImportResult, Importer, SourceError, map_status

REQUIRED_COLUMNS = {"id", "provider", "provider_ref", "amount", "currency", "status", "created_at"}

STATUS_MAP = {
    "completed": Status.COMPLETED,
    "pending": Status.PENDING,
    "failed": Status.FAILED,
    "refunded": Status.REFUNDED,
}


class InternalDbImporter(Importer):
    source = "internal"

    def read(self, path: str | Path) -> ImportResult:
        file = self.check_file(path)
        result = ImportResult(source=self.source, path=file.as_posix())
        try:
            # Read-only öffnen: der Abgleich darf die Produktivdaten nie verändern.
            conn = sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise SourceError(f"Datenbank {file} nicht lesbar: {exc}") from exc
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
            if not columns:
                raise SourceError(f"{file}: Tabelle 'transactions' nicht gefunden")
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise SourceError(f"{file}: Spalten fehlen: {', '.join(sorted(missing))}")
            order_col = "order_no" if "order_no" in columns else "NULL"
            cursor = conn.execute(
                "SELECT id, provider, provider_ref, amount, currency, status, created_at, "
                f"{order_col} FROM transactions ORDER BY id")
            for row in cursor:                       # Cursor streamt: kein komplettes Laden in den Speicher
                result.rows_read += 1
                self._read_row(row, result)
        except sqlite3.Error as exc:
            raise SourceError(f"Datenbank {file} nicht lesbar: {exc}") from exc
        finally:
            conn.close()
        return result

    def _read_row(self, row: tuple, result: ImportResult) -> None:
        row_id, provider, ref, amount, currency, status, created_at, order_no = row
        location = f"id={row_id}"
        ref = str(ref).strip() if ref is not None and str(ref).strip() else None
        try:
            provider = str(provider or "").strip().upper()
            if provider not in ("A", "B"):
                raise ValueError(f"unbekannter Anbieter {provider!r}")
            currency = normalize_currency(currency)
            tx_status, warning = map_status(status, STATUS_MAP)
            tx = Transaction(
                source=self.source, provider=provider, record_id=str(row_id), reference=ref,
                amount=quantize_money(parse_decimal(amount), currency), currency=currency,
                status=tx_status, timestamp=parse_iso_timestamp(created_at),
                raw_status=str(status), note=str(order_no or ""),
            )
        except ValueError as exc:
            result.issues.append(ImportIssue(self.source, location, "error", f"Zeile übersprungen: {exc}", ref))
            return
        if warning:
            result.issues.append(ImportIssue(self.source, location, "warning", warning, ref))
        result.transactions.append(tx)
