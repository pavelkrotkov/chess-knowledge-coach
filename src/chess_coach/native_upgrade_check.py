"""Run a read-only native-upgrade inventory without initializing the database."""

import argparse
import json
import sqlite3

from .native_upgrade_memory import ADDRESS_BYTES, HEAP_BYTES, configure
from .native_upgrade_plan import plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--archive")
    parser.add_argument("--restored")
    parser.add_argument("--codec", choices=("gzip", "zstd"), default="gzip")
    args = parser.parse_args()
    try:
        configure()
        report = plan(
            args.source,
            args.project_root,
            archive=args.archive,
            restored=args.restored,
            codec=args.codec,
        )
        report["process_address_limit_bytes"] = ADDRESS_BYTES
        report["sqlite_hard_heap_limit_bytes"] = HEAP_BYTES
    except (OSError, ValueError, MemoryError, TypeError, OverflowError, sqlite3.Error):
        report = {"status": "unknown", "inventory_complete": False}
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
