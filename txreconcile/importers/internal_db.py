"""Importer für die interne Datenbank (SQLite, Tabelle ``transactions``).

Datenvertrag: Beträge stehen als **ganzzahlige Minor Units** in ``amount_minor`` (INTEGER). Eine Spalte
``amount`` (REAL) ist eine Näherung und wird nur mit ``allow_real_amount=True`` gelesen (Altbestände),
mit dokumentierter Rundung und einer Warnung im Bericht.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Status, Transaction
from ..normalize import (DEFAULT_ID_RULE, ID_RULES, IdRule, normalize_currency, normalize_reference,
                         parse_iso_timestamp, parse_legacy_real, parse_minor_units)
from .base import ImportIssue, ImportResult, Importer, SourceError, map_status

REQUIRED_COLUMNS = {"id", "provider", "provider_ref", "currency", "status", "created_at"}

STATUS_MAP = {
    "completed": Status.COMPLETED,
    "pending": Status.PENDING,
    "failed": Status.FAILED,
    "refunded": Status.REFUNDED,
}


class InternalDbImporter(Importer):
    source = "internal"

    def __init__(self, allow_real_amount: bool = False, id_rules: dict[str, IdRule] | None = None) -> None:
        self.allow_real_amount = allow_real_amount
        self.id_rules = id_rules or ID_RULES

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
            amount_col = self._amount_column(file, columns, result)
            order_col = "order_no" if "order_no" in columns else "NULL"
            cursor = conn.execute(
                f"SELECT id, provider, provider_ref, {amount_col}, typeof({amount_col}), currency, status, "
                f"created_at, {order_col} FROM transactions ORDER BY id")
            for row in cursor:                       # Cursor streamt: kein komplettes Laden in den Speicher
                result.rows_read += 1
                self._read_row(row, amount_col == "amount_minor", result)
        except sqlite3.Error as exc:
            raise SourceError(f"Datenbank {file} nicht lesbar: {exc}") from exc
        finally:
            conn.close()
        return result

    def _amount_column(self, file: Path, columns: set[str], result: ImportResult) -> str:
        if "amount_minor" in columns:
            return "amount_minor"
        if "amount" in columns and self.allow_real_amount:
            result.issues.append(ImportIssue(
                self.source, "Spalte amount", "warning",
                "Beträge stammen aus einer REAL-Spalte (Fließkomma): Genauigkeit nur näherungsweise, "
                "kaufmännisch auf die Währungsgenauigkeit gerundet (Altbestands-Modus)."))
            return "amount"
        if "amount" in columns:
            raise SourceError(
                f"{file}: Spalte 'amount_minor' (INTEGER, Minor Units) fehlt. Die vorhandene Spalte 'amount' "
                f"ist ein Fließkommawert und für Geldbeträge nicht exakt; für Altbestände gibt es den "
                f"ausdrücklichen Modus --allow-real-amount.")
        raise SourceError(f"{file}: Spalte 'amount_minor' fehlt")

    def _read_row(self, row: tuple, strict: bool, result: ImportResult) -> None:
        row_id, provider, ref, amount, amount_type, currency, status, created_at, order_no = row
        location = f"id={row_id}"
        ref = str(ref).strip() if ref is not None and str(ref).strip() else None
        provider = str(provider or "").strip().upper()
        known_provider = provider if provider in ("A", "B") else None
        rule = self.id_rules.get(known_provider, DEFAULT_ID_RULE)
        key = normalize_reference(ref, rule)
        try:
            if known_provider is None:
                raise ValueError(f"unbekannter Anbieter {provider!r}")
            currency = normalize_currency(currency)
            if strict:
                if amount_type != "integer":
                    raise ValueError(f"amount_minor ist kein INTEGER (Typ {amount_type}): {amount!r}")
                value = parse_minor_units(amount, currency)
            else:
                value = parse_legacy_real(amount, currency)
            tx_status, warning = map_status(status, STATUS_MAP)
            tx = Transaction(
                source=self.source, provider=known_provider, record_id=str(row_id), reference=ref,
                amount=value, currency=currency, status=tx_status,
                timestamp=parse_iso_timestamp(created_at), raw_status=str(status),
                note=str(order_no or ""), key=key,
            )
        except ValueError as exc:
            result.issues.append(ImportIssue(self.source, location, "error", f"Zeile übersprungen: {exc}",
                                             ref, known_provider, key))
            return
        if warning:
            result.issues.append(ImportIssue(self.source, location, "warning", warning, ref, known_provider, key))
        result.transactions.append(tx)
