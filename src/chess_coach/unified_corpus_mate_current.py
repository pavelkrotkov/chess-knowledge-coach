"""Recheck a bound corpus mate against its current exact source."""

from .unified_corpus_mate import GOAL, OBJECTIVE, apply, is_source


def require_current(db, row, snapshot_hash):
    if row["source_type"] != "corpus" or row["objective"] != OBJECTIVE:
        return
    if not is_source(row):
        raise ValueError("practice source unavailable or stale")
    from .unified_sources import resolve_source

    source = resolve_source(db, "corpus", row["source_version"], row["source_key"])
    apply(db, source, "corpus", row["source_version"], row["source_key"], GOAL)
    if snapshot_hash(source) != row["snapshot_hash"]:
        raise ValueError("practice source unavailable or stale")
