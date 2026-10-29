"""Validate staged import identity and bounds."""

from .puzzle_import_input import check_digest

OFFICIAL_SOURCE = "https://database.lichess.org/lichess_db_puzzle.csv.zst"


def validate_import(db, version, csv_sha256, archive_sha256, source_url, max_rows, batch_size):
    if db.connection.in_transaction:
        raise RuntimeError("cannot import during an existing transaction")
    if not version or len(version) > 256:
        raise ValueError("a version of at most 256 characters is required")
    check_digest(csv_sha256)
    if not csv_sha256:
        raise ValueError("decoded CSV checksum is required")
    check_digest(archive_sha256)
    if source_url not in {None, OFFICIAL_SOURCE}:
        raise ValueError("only the official puzzle archive URL is supported")
    if not 0 <= max_rows <= 100_000_000 or not 1 <= batch_size <= 500:
        raise ValueError("invalid import bounds")
