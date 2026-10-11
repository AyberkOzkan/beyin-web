from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beyin_web.vault.scan import MarkdownSource


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure read-only vault scans.")
    parser.add_argument("vault", type=Path)
    args = parser.parse_args(argv)
    if not args.vault.is_dir():
        parser.error("vault must be an existing directory")
    source = MarkdownSource(args.vault, min_interval=0)
    start = perf_counter()
    source.snapshot()
    cold_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    snapshot = source.snapshot()
    warm_ms = (perf_counter() - start) * 1000
    print(f"cold_ms: {cold_ms:.3f}")
    print(f"warm_ms: {warm_ms:.3f}")
    for kind, count in sorted(Counter(record.kind for record in snapshot.records.values()).items()):
        print(f"{kind}: {count}")
    print(f"warnings: {len(snapshot.warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
