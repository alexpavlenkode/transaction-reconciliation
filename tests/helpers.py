"""Gemeinsame Test-Helfer."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

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
        got[key] = (sorted(k.value for k in d.kinds), {c: Decimal(str(v)) for c, v in d.impact.items()},
                    d.priority.value)
    want = {}
    for e in expected["discrepancies"]:
        want[(e["internal_id"], e["provider_id"])] = (
            e["issues"], {c: Decimal(v) for c, v in e["impact"].items()}, e["priority"])
    for key in sorted(set(got) | set(want), key=str):
        if key not in got:
            problems.append(f"Abweichung fehlt: {key} erwartet {want[key]}")
        elif key not in want:
            problems.append(f"Abweichung unerwartet: {key} -> {got[key]}")
        else:
            g, w = got[key], want[key]
            if g[0] != w[0] or g[1] != w[1] or (check_priority and g[2] != w[2]):
                problems.append(f"Abweichung {key}: erhalten {g}, erwartet {w}")
    return problems


def load_expected(path: Path = DATA / "expected.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
