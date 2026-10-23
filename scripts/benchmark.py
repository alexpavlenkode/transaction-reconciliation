#!/usr/bin/env python3
"""Einfacher Skalierungstest: erzeugt N zufällige Transaktionen (~6 % Anomalien) und misst die Laufzeit.

    python scripts/benchmark.py 10000 100000 300000

Zeigt je Größe Dauer pro Phase, Spitzen-Speicher und prüft nebenbei, dass alle eingebauten Anomalien
exakt wiedergefunden werden (Korrektheit bleibt auch bei Last gewährleistet).
"""
from __future__ import annotations

import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_testdata import generate  # noqa: E402
from tests.helpers import config_for, diff_with_expected, load_expected  # noqa: E402
from txreconcile.discrepancies import find_discrepancies  # noqa: E402
from txreconcile.importers import InternalDbImporter, ProviderACsvImporter, ProviderBJsonImporter  # noqa: E402
from txreconcile.matching import match_transactions  # noqa: E402
from txreconcile.reconcile import reconcile  # noqa: E402
from txreconcile.report import write_reports  # noqa: E402


def run(size: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate(out, seed=1, curated=False, bulk=size)
        expected = load_expected(out / "expected.json")
        config = config_for(expected)

        t0 = time.perf_counter()
        internal = InternalDbImporter().read(out / "internal.db")
        providers = [ProviderACsvImporter().read(out / "provider_a.csv"),
                     ProviderBJsonImporter().read(out / "provider_b.json")]
        t_import = time.perf_counter() - t0

        t0 = time.perf_counter()
        provider_txs = [tx for p in providers for tx in p.transactions]
        matching = match_transactions(internal.transactions, provider_txs, config)
        t_match = time.perf_counter() - t0

        t0 = time.perf_counter()
        find_discrepancies(matching, config)
        t_disc = time.perf_counter() - t0
        result = reconcile(internal, providers, config)
        t0 = time.perf_counter()
        write_reports(result, out / "reports")
        t_report = time.perf_counter() - t0

        problems = diff_with_expected(result, expected, check_priority=False)
        total = t_import + t_match + t_disc

        # Speicher separat messen: tracemalloc bremst stark und würde die Zeiten oben verfälschen.
        tracemalloc.start()
        reconcile(InternalDbImporter().read(out / "internal.db"),
                  [ProviderACsvImporter().read(out / "provider_a.csv"),
                   ProviderBJsonImporter().read(out / "provider_b.json")], config)
        peak = tracemalloc.get_traced_memory()[1] / 1e6
        tracemalloc.stop()
        print(f"{size:>9,} | import {t_import:6.2f}s | match {t_match:6.2f}s | discrepancies {t_disc:5.2f}s | "
              f"reports {t_report:5.2f}s | pipeline {total:6.2f}s ({size / total:>9,.0f} tx/s) | "
              f"peak {peak:6.0f} MB | {'korrekt' if not problems else f'{len(problems)} ABWEICHUNGEN'}")


if __name__ == "__main__":
    for arg in sys.argv[1:] or ["10000", "100000"]:
        run(int(arg))
