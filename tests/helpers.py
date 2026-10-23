"""Gemeinsame Test-Helfer."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from txreconcile.config import ReconcileConfig
from txreconcile.models import Status, Transaction

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
T0 = datetime(2025, 3, 3, 10, 0, tzinfo=timezone.utc)


def tx(source: str, record_id: str, ref: str | None, amount: str = "100.00", *, provider: str = "A",
       currency: str = "EUR", status: Status = Status.COMPLETED, minutes: int = 0) -> Transaction:
    return Transaction(source=source, provider=provider, record_id=record_id, reference=ref,
                       amount=Decimal(amount), currency=currency, status=status,
                       timestamp=T0 + timedelta(minutes=minutes))


def internal(record_id: str, ref: str | None, amount: str = "100.00", **kw) -> Transaction:
    return tx("internal", record_id, ref, amount, **kw)


def provider(record_id: str, amount: str = "100.00", **kw) -> Transaction:
    return tx("provider_a", record_id, record_id, amount, **kw)


def load_expected(path: Path = DATA / "expected.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def config_for(expected: dict) -> ReconcileConfig:
    """Konfiguration passend zur Ground Truth (Stichtag und Frist stehen in ``expected.json``)."""
    return ReconcileConfig(as_of=datetime.fromisoformat(expected["as_of"]),
                           settlement_lag=timedelta(days=expected["settlement_lag_days"]))


def canonical(result) -> dict:
    """Vollständiger, reihenfolgetreuer Inhalt eines Ergebnisses – zum Vergleich zweier Läufe."""
    return {
        "matches": sorted((m.internal.record_id, m.provider.record_id, m.method, m.confidence)
                          for m in result.matching.matches),
        "discrepancies": [(d.priority.value, d.certainty.value, [k.value for k in d.kinds],
                           d.internal.record_id if d.internal else None,
                           d.provider.record_id if d.provider else None,
                           sorted((c, str(v)) for c, v in d.impact.items()),
                           sorted((c, str(v)) for c, v in d.affected.items()), d.description)
                          for d in result.discrepancies],
        "net": sorted((c, str(v)) for c, v in result.summary.net_impact.items()),
        "undefined": sorted((c, str(v)) for c, v in result.summary.undefined_affected.items()),
    }


def diff_with_expected(result, expected: dict, check_priority: bool = True) -> list[str]:
    """Vergleicht ein Abgleichsergebnis mit der Ground Truth aus ``expected.json``; liefert Abweichungen."""
    problems: list[str] = []

    got_matched = {(int(m.internal.record_id), m.provider.record_id, m.method) for m in result.matching.matches}
    want_matched = {(e["internal_id"], e["provider_id"], e["method"]) for e in expected["matched"]}
    for item in sorted(got_matched ^ want_matched, key=str):
        problems.append(f"Zuordnung {'unerwartet' if item in got_matched else 'fehlt'}: {item}")

    got = {}
    for d in result.discrepancies:
        key = (int(d.internal.record_id) if d.internal else None, d.provider.record_id if d.provider else None)
        got[key] = {"issues": sorted(k.value for k in d.kinds),
                    "impact": {c: Decimal(str(v)) for c, v in d.impact.items()},
                    "affected": {c: Decimal(str(v)) for c, v in d.affected.items()},
                    "certainty": d.certainty.value, "priority": d.priority.value}
    want = {}
    for e in expected["discrepancies"]:
        want[(e["internal_id"], e["provider_id"])] = {
            "issues": e["issues"], "impact": {c: Decimal(v) for c, v in e["impact"].items()},
            "affected": None if e["affected"] is None else {c: Decimal(v) for c, v in e["affected"].items()},
            "certainty": e["certainty"], "priority": e["priority"]}
    for key in sorted(set(got) | set(want), key=str):
        if key not in got:
            problems.append(f"Abweichung fehlt: {key} erwartet {want[key]}")
        elif key not in want:
            problems.append(f"Abweichung unerwartet: {key} -> {got[key]}")
        else:
            for field in ("issues", "impact", "certainty", "affected", "priority"):
                if field == "priority" and not check_priority:
                    continue
                if want[key][field] is None:
                    continue
                if got[key][field] != want[key][field]:
                    problems.append(f"Abweichung {key}: {field} erhalten {got[key][field]}, erwartet {want[key][field]}")
    return problems
