"""Report Radon complexity and maintainability for every production Python file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.metrics import measure
from scripts.sources import production_files

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail on metric violations (default)")
    mode.add_argument(
        "--report-only", action="store_true", help="report violations without failing"
    )
    args = parser.parse_args()
    failed = False
    try:
        for path in production_files(ROOT):
            mi, callables = measure(path.read_text(encoding="utf-8"))
            print(f"{path.relative_to(ROOT)}: MI {mi:.2f} (must be > 50)")
            failed |= mi <= 50
            for line, name, complexity in callables:
                print(f"  {line}: {name}: CC {complexity} (must be <= 8)")
                failed |= complexity > 8
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"quality check failed: {exc}", file=sys.stderr)
        return 1
    if failed and args.report_only:
        print("Metric violations found; report-only mode does not enforce limits.")
    return int(failed and not args.report_only)


if __name__ == "__main__":
    raise SystemExit(main())
