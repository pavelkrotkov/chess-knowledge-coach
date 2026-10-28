"""Import only supported games within an existing window transaction."""

from .db import Database
from .ingest import ingest_in_transaction
from .lichess_support import supported


def import_records(db: Database, records: list[str]) -> dict[str, int]:
    totals = {"games": 0, "positions": 0, "unsupported": 0}
    for raw in records:
        if not supported(raw):
            totals["unsupported"] += 1
            continue
        imported = ingest_in_transaction(db, raw, source="lichess", raw_pgn_override=raw)
        for key in ("games", "positions"):
            totals[key] += imported[key]
    return totals
