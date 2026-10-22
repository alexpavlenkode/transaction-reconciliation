"""Importer für Zahlungsdienstleister B (JSON, Beträge in Minor Units, ISO-8601 mit Offset).

Beispiel::

    {"transactions": [
      {"id": "bpay_9f3a1c2b7d", "created": "2025-03-03T12:15:22+02:00",
       "amount": {"minor": 123456, "currency": "EUR"}, "state": "captured"}
    ]}

Hinweis zur Skalierung: ``json.load`` lädt die Datei komplett. Für sehr große Exporte wäre
JSON Lines oder ein Streaming-Parser (z. B. ``ijson``) der nächste Schritt (siehe README).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..models import Status, Transaction
from ..normalize import normalize_currency, parse_iso_timestamp, parse_minor_units
from .base import ImportIssue, ImportResult, Importer, SourceError, map_status

STATUS_MAP = {
    "captured": Status.COMPLETED,
    "pending": Status.PENDING,
    "declined": Status.FAILED,
    "refunded": Status.REFUNDED,
}


class ProviderBJsonImporter(Importer):
    source = "provider_b"
    provider = "B"

    def read(self, path: str | Path) -> ImportResult:
        file = self.check_file(path)
        result = ImportResult(source=self.source, path=file.as_posix())
        try:
            with file.open(encoding="utf-8-sig") as handle:
                document = json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceError(f"{file} nicht lesbar: {exc}") from exc
        records = document.get("transactions") if isinstance(document, dict) else None
        if not isinstance(records, list):
            raise SourceError(f"{file}: Feld 'transactions' (Liste) fehlt")
        for index, record in enumerate(records):
            result.rows_read += 1
            self._read_record(record, f"transactions[{index}]", result)
        return result

    def _read_record(self, record: object, location: str, result: ImportResult) -> None:
        ref = None
        try:
            if not isinstance(record, dict):
                raise ValueError("Eintrag ist kein Objekt")
            ref = str(record["id"]).strip() if record.get("id") not in (None, "") else None
            if ref is None:
                raise ValueError("Feld 'id' fehlt")
            amount = record.get("amount")
            if not isinstance(amount, dict) or "minor" not in amount:
                raise ValueError("Feld 'amount.minor' fehlt")
            currency = normalize_currency(amount.get("currency"))
            status, warning = map_status(record.get("state"), STATUS_MAP)
            tx = Transaction(
                source=self.source, provider="B", record_id=ref, reference=ref,
                amount=parse_minor_units(amount["minor"], currency), currency=currency,
                status=status, timestamp=parse_iso_timestamp(record.get("created")),
                raw_status=str(record.get("state", "")),
            )
        except ValueError as exc:
            result.issues.append(ImportIssue(self.source, location, "error", f"Eintrag übersprungen: {exc}", ref))
            return
        if warning:
            result.issues.append(ImportIssue(self.source, location, "warning", warning, ref))
        result.transactions.append(tx)
