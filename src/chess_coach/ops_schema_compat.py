"""Prepare a private schema-32 compatibility attestation."""

import os
import sqlite3
from pathlib import Path

from .schema_compat import attest, configured


def main():
    path = Path(os.environ["CHESS_DB"]).resolve(strict=True)
    if not configured(path):
        raise SystemExit("Schema compatibility must be explicitly selected.")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        connection.execute("PRAGMA query_only=ON")
        attest(path, connection)
    finally:
        connection.close()
    print("Private schema compatibility attestation prepared.")


if __name__ == "__main__":
    main()
