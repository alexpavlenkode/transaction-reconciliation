#!/usr/bin/env python3
"""Erzeugt deterministische Testdaten für den Transaktionsabgleich.

Drei Quellen in drei unterschiedlichen Formaten:

* ``internal.db``      – SQLite, interne Buchungen (Beträge als REAL, Zeiten UTC)
* ``provider_a.csv``   – Zahlungsdienstleister A: CSV, ``;``-getrennt, deutsche
                         Zahlen- und Datumsformate, deutsche Statuswerte
* ``provider_b.json``  – Zahlungsdienstleister B: JSON, Beträge in Minor Units
                         (Cent), ISO-8601-Zeitstempel mit Zeitzonen-Offset

Zusätzlich wird ``expected.json`` geschrieben: der von Hand festgelegte
Erwartungswert (Ground Truth) für jede eingebaute Konstellation. Die Tests
vergleichen das Abgleichsergebnis dagegen – unabhängig von der Implementierung.

Aufruf::

    python scripts/generate_testdata.py                      # data/ (kuratierter Satz)
    python scripts/generate_testdata.py --bulk 50000 --out build/bulk   # Lasttest
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

STATUS_INTERNAL = {"COMPLETED": "completed", "PENDING": "pending", "FAILED": "failed", "REFUNDED": "refunded"}
STATUS_A = {"COMPLETED": "ABGESCHLOSSEN", "PENDING": "AUSSTEHEND", "FAILED": "FEHLGESCHLAGEN", "REFUNDED": "ERSTATTET"}
STATUS_B = {"COMPLETED": "captured", "PENDING": "pending", "FAILED": "declined", "REFUNDED": "refunded"}
EXPONENTS = {"JPY": 0}
UTC = timezone.utc
BASE_TIME = datetime(2025, 3, 1, 8, 0, tzinfo=UTC)

CSV_HEADER = ["Transaktions-ID", "Zeitstempel (UTC)", "Betrag", "Waehrung", "Status"]


def money(value: str | Decimal) -> Decimal:
    return Decimal(value)


def german_amount(amount: Decimal) -> str:
    """1234.5 -> '1.234,50'"""
    text = f"{amount:,.2f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


class Dataset:
    """Sammelt Zeilen der drei Quellen sowie die erwarteten Ergebnisse."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.internal: list[dict] = []
        self.rows_a: list[dict] = []
        self.rows_b: list[dict] = []
        self.expected_matched: list[dict] = []
        self.expected_discrepancies: list[dict] = []
        self.expected_import = {"errors": 0, "warnings": 0}
        self._next_id = 1001
        self._used_refs: set[str] = set()

    # -- Bausteine ---------------------------------------------------------

    def ref(self, provider: str) -> str:
        while True:
            ref = (f"ATX-{self.rng.randrange(10_000_000, 99_999_999)}" if provider == "A"
                   else f"bpay_{self.rng.getrandbits(40):010x}")
            if ref not in self._used_refs:
                self._used_refs.add(ref)
                return ref

    def timestamp(self) -> datetime:
        return (BASE_TIME + timedelta(seconds=self.rng.randrange(0, 27 * 86400))).replace(microsecond=0)

    def add_internal(self, provider, ref_text, amount, currency, status, ts, *, order=True) -> int:
        row_id = self._next_id
        self._next_id += 1
        self.internal.append({
            "id": row_id, "provider": provider, "provider_ref": ref_text,
            "amount": float(amount), "currency": currency,
            "status": STATUS_INTERNAL[status], "created_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "order_no": f"SO-{row_id * 7 + 20000}" if order else None,
        })
        return row_id

    def add_provider(self, provider, ref, amount, currency, status, ts) -> None:
        if provider == "A":
            self.rows_a.append({
                "Transaktions-ID": ref,
                "Zeitstempel (UTC)": ts.strftime("%d.%m.%Y %H:%M:%S"),
                "Betrag": amount if isinstance(amount, str) else german_amount(amount),
                "Waehrung": currency,
                "Status": STATUS_A.get(status, status),
            })
        else:
            exp = EXPONENTS.get(currency, 2)
            if self.rng.random() < 0.3:
                stamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                stamp = ts.astimezone(timezone(timedelta(hours=2))).isoformat()
            self.rows_b.append({
                "id": ref,
                "created": stamp,
                "amount": {"minor": int(amount.scaleb(exp)), "currency": currency},
                "state": STATUS_B.get(status, status),
            })

    # -- Szenarien ---------------------------------------------------------

    def pair(self, provider, amount, currency="EUR", status="COMPLETED", *, p_amount=None, p_currency=None,
             p_status=None, p_ref=None, messy=False, issues=(), impact=None, priority=None, method="exact"):
        """Beide Seiten vorhanden. ``issues``/``impact``/``priority`` = Erwartung."""
        amount = money(amount)
        ref = self.ref(provider)
        ts = self.timestamp()
        ref_text = ref
        if messy:  # unsaubere interne Schreibweise: Normalisierung muss das auffangen
            ref_text = f" {ref.lower()} " if provider == "A" else ref.upper()
        iid = self.add_internal(provider, ref_text, amount, currency, status, ts)
        provider_ref = p_ref(ref) if p_ref else ref
        self.add_provider(provider, provider_ref, money(p_amount) if p_amount is not None else amount,
                          p_currency or currency, p_status or status,
                          ts + timedelta(seconds=self.rng.randrange(5, 120)))
        self.expected_matched.append({"internal_id": iid, "provider_id": provider_ref, "method": method})
        if issues:
            self.expect(iid, provider_ref, issues, impact, priority)
        return iid, ref, ts

    def internal_only(self, provider, amount, currency="EUR", status="COMPLETED", *, null_ref=False,
                      ref=None, ts=None, issues=("MISSING_IN_PROVIDER",), impact=None, priority=None):
        amount = money(amount)
        ref = ref or self.ref(provider)
        iid = self.add_internal(provider, None if null_ref else ref, amount, currency, status, ts or self.timestamp())
        self.expect(iid, None, issues, impact, priority)
        return iid, ref

    def provider_only(self, provider, amount, currency="EUR", status="COMPLETED", *, ref=None, ts=None,
                      issues=("MISSING_IN_DB",), impact=None, priority=None):
        ref = ref or self.ref(provider)
        self.add_provider(provider, ref, money(amount), currency, status, ts or self.timestamp())
        self.expect(None, ref, issues, impact, priority)
        return ref

    def expect(self, internal_id, provider_id, issues, impact, priority) -> None:
        self.expected_discrepancies.append({
            "internal_id": internal_id, "provider_id": provider_id,
            "issues": sorted(issues), "impact": impact or {}, "priority": priority,
        })


def corrupt_digit(ref: str) -> str:
    """Tippfehler: eine Ziffer wird zum Buchstaben 'O' (lesbar, aber nicht identisch)."""
    for idx in range(len(ref) - 1, -1, -1):
        if ref[idx].isdigit():
            return ref[:idx] + "O" + ref[idx + 1:]
    return ref + "O"


def build_curated(ds: Dataset) -> None:
    # ---- Provider A: saubere Treffer (13) ---------------------------------
    for idx, amount in enumerate(["49.90", "120.00", "1234.56", "15.00", "89.99",
                                  "560.00", "23.45", "310.75", "999.00", "7.50"]):
        ds.pair("A", amount, messy=idx % 3 == 0)
    ds.pair("A", "250.00", currency="USD")
    ds.pair("A", "64.00", status="REFUNDED")
    ds.pair("A", "18.00", status="FAILED")
    ds.pair("A", "27.90", status="PENDING")

    # ---- Provider A: Betragsabweichungen ----------------------------------
    ds.pair("A", "1250.00", p_amount="1205.00", issues=["AMOUNT_MISMATCH"],
            impact={"EUR": "-45.00"}, priority="LOW")                      # Zahlendreher
    ds.pair("A", "899.00", p_amount="989.00", issues=["AMOUNT_MISMATCH"],
            impact={"EUR": "90.00"}, priority="MEDIUM")
    ds.pair("A", "12000.00", p_amount="1200.00", issues=["AMOUNT_MISMATCH"],
            impact={"EUR": "-10800.00"}, priority="HIGH")                   # Dezimalfehler

    # ---- Provider A: Statusabweichungen -----------------------------------
    ds.pair("A", "349.90", status="COMPLETED", p_status="FAILED", issues=["STATUS_MISMATCH"],
            impact={"EUR": "-349.90"}, priority="MEDIUM")
    ds.pair("A", "75.00", status="PENDING", p_status="COMPLETED", issues=["STATUS_MISMATCH"],
            impact={"EUR": "75.00"}, priority="MEDIUM")
    ds.pair("A", "2500.00", status="COMPLETED", p_status="REFUNDED", issues=["STATUS_MISMATCH"],
            impact={"EUR": "-2500.00"}, priority="HIGH")
    ds.pair("A", "33.00", status="PENDING", p_status="FAILED", issues=["STATUS_MISMATCH"],
            impact={}, priority="LOW")                                      # beide nicht verbucht
    # Betrag UND Status weichen ab: Auswirkung darf nur einmal gezählt werden
    ds.pair("A", "500.00", status="COMPLETED", p_amount="450.00", p_status="PENDING",
            issues=["AMOUNT_MISMATCH", "STATUS_MISMATCH"], impact={"EUR": "-500.00"}, priority="HIGH")

    # ---- Provider A: fehlt in der Abrechnung ------------------------------
    p1_ts = ds.timestamp()
    p1_iid, p1_ref = ds.internal_only("A", "1800.00", ts=p1_ts, impact={"EUR": "-1800.00"}, priority="HIGH")
    ds.internal_only("A", "42.00", impact={"EUR": "-42.00"}, priority="LOW")
    ds.internal_only("A", "120.00", status="PENDING", impact={}, priority="LOW")  # vermutlich noch offen
    ds.internal_only("A", "64.00", null_ref=True, impact={"EUR": "-64.00"}, priority="MEDIUM")
    # Abrechnungszeile ist unlesbar (Betrag "n/a") -> Importfehler + fehlt in Abrechnung
    iid, ref = ds.internal_only("A", "410.00", impact={"EUR": "-410.00"}, priority="MEDIUM")
    ds.add_provider("A", ref, "n/a", "EUR", "COMPLETED", ds.timestamp())
    ds.expected_import["errors"] += 1

    # ---- Provider A: fehlt in der Datenbank -------------------------------
    # Referenz fast identisch zu p1_ref (letzte Ziffer anders), aber Betrag weit weg:
    # darf NICHT unscharf zugeordnet werden (Schutz gegen falsche Treffer).
    decoy_ref = p1_ref[:-1] + ("1" if p1_ref[-1] != "1" else "2")
    ds._used_refs.add(decoy_ref)
    ds.provider_only("A", "640.00", ref=decoy_ref, ts=p1_ts + timedelta(hours=2),
                     impact={"EUR": "640.00"}, priority="HIGH")
    ds.provider_only("A", "19.99", impact={"EUR": "19.99"}, priority="LOW")

    # ---- Provider A: Duplikat in der Abrechnung ---------------------------
    iid, ref, ts = ds.pair("A", "310.00")
    ds.add_provider("A", ref, Decimal("310.00"), "EUR", "COMPLETED", ts + timedelta(minutes=3))
    ds.expect(None, ref, ["DUPLICATE_IN_PROVIDER"], {"EUR": "310.00"}, "MEDIUM")

    # ---- Provider A: unscharfe Zuordnung ----------------------------------
    ds.pair("A", "180.00", p_ref=corrupt_digit, issues=["REFERENCE_MISMATCH"],
            impact={}, priority="LOW", method="fuzzy")                      # Tippfehler in der Referenz
    ds.pair("A", "220.00", p_amount="202.00", p_ref=lambda r: r[1:],         # führendes 'A' fehlt
            issues=["REFERENCE_MISMATCH", "AMOUNT_MISMATCH"], impact={"EUR": "-18.00"},
            priority="LOW", method="fuzzy")

    # ---- Provider B: saubere Treffer (9) ----------------------------------
    for idx, amount in enumerate(["35.00", "1480.00", "56.20", "210.50", "9.99", "775.00"]):
        ds.pair("B", amount, messy=idx % 2 == 0)
    ds.pair("B", "15800", currency="JPY")                                   # 0 Nachkommastellen
    ds.pair("B", "99.00", currency="USD")
    ds.pair("B", "129.00", status="REFUNDED")

    # ---- Provider B: Abweichungen -----------------------------------------
    ds.pair("B", "200.00", currency="EUR", p_currency="USD", issues=["CURRENCY_MISMATCH"],
            impact={"USD": "200.00", "EUR": "-200.00"}, priority="HIGH")
    ds.pair("B", "75.50", p_amount="57.50", issues=["AMOUNT_MISMATCH"],
            impact={"EUR": "-18.00"}, priority="LOW")
    ds.pair("B", "1150.00", p_status="FAILED", issues=["STATUS_MISMATCH"],
            impact={"EUR": "-1150.00"}, priority="HIGH")
    ds.pair("B", "330.00", p_status="chargeback_initiated", issues=["STATUS_MISMATCH"],
            impact={"EUR": "-330.00"}, priority="MEDIUM")                    # unbekannter Status
    ds.expected_import["warnings"] += 1
    ds.internal_only("B", "210.00", impact={"EUR": "-210.00"}, priority="MEDIUM")
    ds.provider_only("B", "88.00", impact={"EUR": "88.00"}, priority="MEDIUM")

    # Doppelbuchung in der Datenbank (zweite Buchung 5 Min. später)
    iid, ref, ts = ds.pair("B", "145.00")
    dup_id = ds.add_internal("B", ref, Decimal("145.00"), "EUR", "COMPLETED", ts + timedelta(minutes=5))
    ds.expect(dup_id, None, ["DUPLICATE_IN_DB"], {"EUR": "-145.00"}, "MEDIUM")

    ds.pair("B", "62.00", p_ref=lambda r: r[:8] + r[9:], issues=["REFERENCE_MISMATCH"],
            impact={}, priority="LOW", method="fuzzy")                      # ein Zeichen fehlt

    # Datensatz ohne ID -> nicht abgleichbar, Importfehler
    ds.rows_b.append({"created": "2025-03-12T10:00:00+02:00",
                      "amount": {"minor": 1234, "currency": "EUR"}, "state": "captured"})
    ds.expected_import["errors"] += 1


def build_bulk(ds: Dataset, count: int) -> None:
    """Zufällige Masse mit ~6 % Anomalien für Last-/Performancetests."""
    for _ in range(count):
        provider = "A" if ds.rng.random() < 0.55 else "B"
        amount = Decimal(ds.rng.randint(100, 250_000)) / 100
        roll = ds.rng.random()
        if roll < 0.94:
            ds.pair(provider, amount, messy=ds.rng.random() < 0.2)
        elif roll < 0.955:
            ds.pair(provider, amount, p_amount=amount + Decimal("1.00"),
                    issues=["AMOUNT_MISMATCH"], impact={"EUR": "1.00"}, priority="LOW")
        elif roll < 0.97:
            ds.pair(provider, amount, p_status="FAILED", issues=["STATUS_MISMATCH"],
                    impact={"EUR": f"{-amount:.2f}"}, priority=None)
        elif roll < 0.985:
            ds.internal_only(provider, amount, impact={"EUR": f"{-amount:.2f}"}, priority=None)
        else:
            ds.provider_only(provider, amount, impact={"EUR": f"{amount:.2f}"}, priority=None)


# ---- Ausgabe ---------------------------------------------------------------

def write_sqlite(path: Path, rows: list[dict]) -> None:
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE transactions (
                id           INTEGER PRIMARY KEY,
                provider     TEXT NOT NULL CHECK (provider IN ('A', 'B')),
                provider_ref TEXT,
                amount       REAL NOT NULL,
                currency     TEXT NOT NULL,
                status       TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                order_no     TEXT
            );
            CREATE INDEX idx_transactions_ref ON transactions (provider, provider_ref);
        """)
        conn.executemany(
            "INSERT INTO transactions VALUES (:id, :provider, :provider_ref, :amount, :currency,"
            " :status, :created_at, :order_no)", rows)
    conn.close()


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
        fh.write("\r\n")  # typische Leerzeile am Dateiende


def write_json(path: Path, document: dict) -> None:
    # newline="\n": auf jedem Betriebssystem dieselben Bytes (sonst CRLF unter Windows)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(document, fh, indent=1, ensure_ascii=False)


def generate(out: Path, seed: int = 2025, curated: bool = True, bulk: int = 0) -> Dataset:
    out.mkdir(parents=True, exist_ok=True)
    ds = Dataset(seed)
    if curated:
        build_curated(ds)
    if bulk:
        build_bulk(ds, bulk)
    ds.rng.shuffle(ds.rows_a)  # Dateien sind nicht in der Reihenfolge der Datenbank sortiert
    ds.rng.shuffle(ds.rows_b)

    write_sqlite(out / "internal.db", ds.internal)
    write_csv(out / "provider_a.csv", ds.rows_a)
    write_json(out / "provider_b.json", {"provider": "B", "exported_at": "2025-04-01T00:00:00+02:00",
                                         "transactions": ds.rows_b})
    write_json(out / "expected.json", {
        "matched": ds.expected_matched,
        "discrepancies": ds.expected_discrepancies,
        "import_issues": ds.expected_import,
        "counts": {"internal": len(ds.internal), "provider_a": len(ds.rows_a), "provider_b": len(ds.rows_b)},
    })
    return ds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--bulk", type=int, default=0, help="N zufällige Zusatz-Transaktionen (ohne kuratierten Satz)")
    args = parser.parse_args()
    ds = generate(args.out, args.seed, curated=not args.bulk, bulk=args.bulk)
    print(f"{len(ds.internal)} interne Buchungen, {len(ds.rows_a)} Zeilen A, {len(ds.rows_b)} Einträge B -> {args.out}")


if __name__ == "__main__":
    main()
