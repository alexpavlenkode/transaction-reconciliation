"""Maschinenlesbare Ausgaben (JSON, CSV) – dieselbe Datenbasis speist auch das HTML-Dashboard.

Der Inhalt hängt nur von Eingabedaten und Konfiguration ab (kein Erzeugungszeitpunkt): derselbe Lauf
liefert byte-identische Dateien.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from ..formatting import CERTAINTY_LABELS, KIND_LABELS, PRIORITY_LABELS
from ..models import Discrepancy, Transaction
from ..reconcile import ReconciliationResult


def _money(value: Decimal) -> str:
    return format(value, "f")


def amounts_to_dict(amounts: dict[str, Decimal]) -> dict[str, str]:
    return {currency: _money(value) for currency, value in sorted(amounts.items())}


def tx_to_dict(tx: Transaction | None) -> dict | None:
    if tx is None:
        return None
    return {
        "source": tx.source, "record_id": tx.record_id, "reference": tx.reference,
        "amount": _money(tx.amount), "currency": tx.currency, "status": tx.status.value,
        "raw_status": tx.raw_status, "timestamp": tx.timestamp.isoformat(), "note": tx.note,
    }


def discrepancy_to_dict(number: int, item: Discrepancy) -> dict:
    return {
        "id": f"D-{number:03d}",
        "priority": item.priority.value,
        "priority_label": PRIORITY_LABELS[item.priority],
        "certainty": item.certainty.value,
        "certainty_label": CERTAINTY_LABELS[item.certainty],
        "kinds": [kind.value for kind in item.kinds],
        "kind_labels": [KIND_LABELS[kind] for kind in item.kinds],
        "provider": item.provider_code,
        "internal": tx_to_dict(item.internal),
        "provider_tx": tx_to_dict(item.provider),
        "effect_defined": item.effect_defined,
        "impact": amounts_to_dict(item.impact),          # leer, wenn nicht bestimmbar oder null
        "affected": amounts_to_dict(item.affected),      # betroffener Betrag – nie Teil der Summen
        "description": item.description,
        "action": item.action,
        "match_method": item.match.method if item.match and item.internal and item.provider else None,
    }


def result_to_dict(result: ReconciliationResult, matched_limit: int | None = None) -> dict:
    """Gesamtergebnis als JSON-fähiges Dict. ``matched_limit`` kürzt nur die Liste der Treffer
    (für das HTML-Dashboard); ``matched_total`` nennt immer die tatsächliche Anzahl."""
    summary = result.summary
    flagged = result.flagged_matches
    config = result.config
    return {
        "as_of": config.as_of.isoformat(timespec="seconds") if config.as_of else None,
        "incomplete": result.incomplete,
        "incomplete_reasons": result.incomplete_reasons,
        "config": {
            "settlement_lag_days": config.settlement_lag.total_seconds() / 86400,
            "amount_tolerance": _money(config.amount_tolerance),
            "fuzzy_enabled": config.fuzzy_enabled,
            "fuzzy_time_window_days": config.fuzzy_time_window.total_seconds() / 86400,
            "fuzzy_min_ref_similarity": config.fuzzy_min_ref_similarity,
            "fuzzy_min_ref_similarity_if_amount_differs": config.fuzzy_min_ref_similarity_if_amount_differs,
            "fuzzy_min_score": config.fuzzy_min_score,
            "default_thresholds": {"high": _money(config.high_threshold), "medium": _money(config.medium_threshold)},
            "currency_thresholds": {c: {"high": _money(h), "medium": _money(m)}
                                    for c, (h, m) in sorted(config.currency_thresholds.items())},
        },
        "sources": [{
            "source": s.source, "path": s.path, "rows_read": s.rows_read,
            "imported": len(s.transactions), "errors": len(s.errors), "warnings": len(s.warnings),
        } for s in result.sources],
        "summary": {
            "internal_total": summary.internal_total, "provider_total": summary.provider_total,
            "matched": summary.matched, "matched_exact": summary.exact, "matched_fuzzy": summary.fuzzy,
            "unmatched_internal": summary.unmatched_internal, "unmatched_provider": summary.unmatched_provider,
            "duplicates": summary.duplicates, "discrepancies": summary.discrepancy_count,
            "clean_matches": summary.clean_matches,
            "match_rate": round(summary.match_rate, 4), "clean_rate": round(summary.clean_rate, 4),
            "by_priority": {p.value: n for p, n in summary.by_priority.items()},
            "by_certainty": {c.value: n for c, n in summary.by_certainty.items()},
            "by_kind": {k.value: {"count": s.count, "impact": amounts_to_dict(s.impact),
                                  "undefined": s.undefined,
                                  "affected_undefined": amounts_to_dict(s.affected_undefined)}
                        for k, s in summary.by_kind.items()},
            "net_impact": amounts_to_dict(summary.net_impact),
            "gross_impact": amounts_to_dict(summary.gross_impact),
            "undefined_count": summary.undefined_count,
            "undefined_affected": amounts_to_dict(summary.undefined_affected),
            "preliminary_count": summary.preliminary_count,
            "providers": [{
                "provider": p.provider, "internal_total": p.internal_total, "provider_total": p.provider_total,
                "matched": p.matched, "exact": p.exact, "fuzzy": p.fuzzy,
                "missing_in_provider": p.missing_in_provider, "missing_in_db": p.missing_in_db,
                "duplicates": p.duplicates, "discrepancies": p.discrepancies, "impact": amounts_to_dict(p.impact),
                "undefined": p.undefined, "affected_undefined": amounts_to_dict(p.affected_undefined),
            } for p in summary.providers],
        },
        "discrepancies": [discrepancy_to_dict(n, d) for n, d in enumerate(result.discrepancies, 1)],
        "matched_total": len(result.matching.matches),
        "matched": [{
            "internal": tx_to_dict(m.internal), "provider_tx": tx_to_dict(m.provider),
            "provider": m.internal.provider, "method": m.method, "confidence": m.confidence,
            "has_discrepancy": (m.internal.record_id, m.provider.record_id) in flagged,
        } for m in result.sorted_matches()[:matched_limit]],
        "import_issues": [{
            "source": i.source, "location": i.location, "severity": i.severity,
            "message": i.message, "reference": i.reference,
        } for i in result.import_issues],
    }


def write_json(result: ReconciliationResult, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result_to_dict(result), handle, indent=2, ensure_ascii=False)


def _amounts_text(amounts: dict[str, str]) -> str:
    return "; ".join(f"{currency}:{value}" for currency, value in amounts.items())


def write_discrepancies_csv(result: ReconciliationResult, path: Path) -> None:
    header = ["id", "priority", "certainty", "kinds", "provider", "db_id", "db_reference", "db_amount",
              "db_currency", "db_status", "db_time", "provider_id", "provider_amount", "provider_currency",
              "provider_status", "provider_time", "impact", "affected", "description", "action"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:      # BOM: Excel erkennt UTF-8
        writer = csv.writer(handle)
        writer.writerow(header)
        for number, item in enumerate(result.discrepancies, 1):
            row = discrepancy_to_dict(number, item)
            db, pv = row["internal"] or {}, row["provider_tx"] or {}
            writer.writerow([
                row["id"], row["priority"], row["certainty"], "|".join(row["kinds"]), row["provider"],
                db.get("record_id", ""), db.get("reference") or "", db.get("amount", ""), db.get("currency", ""),
                db.get("status", ""), db.get("timestamp", ""),
                pv.get("record_id", ""), pv.get("amount", ""), pv.get("currency", ""),
                pv.get("status", ""), pv.get("timestamp", ""),
                # leer = nicht bestimmbar bzw. null; Unterscheidung über die Spalte "certainty"
                _amounts_text(row["impact"]), _amounts_text(row["affected"]), row["description"], row["action"],
            ])


def write_matched_csv(result: ReconciliationResult, path: Path) -> None:
    flagged = result.flagged_matches
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["provider", "db_id", "provider_id", "method", "confidence", "amount", "currency",
                         "db_status", "provider_status", "has_discrepancy"])
        for m in result.sorted_matches():
            writer.writerow([
                m.internal.provider, m.internal.record_id, m.provider.record_id, m.method, m.confidence,
                _money(m.internal.amount), m.internal.currency, m.internal.status.value, m.provider.status.value,
                "yes" if (m.internal.record_id, m.provider.record_id) in flagged else "no",
            ])
