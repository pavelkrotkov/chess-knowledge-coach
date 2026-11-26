"""Rebind a completed window to its exact indexed corpus rows."""

from .capture_corpus_storage import POLICY
from .fact_fingerprint import canonical, digest
from .related_capture_candidates import _corpus
from .related_corpus_window import corpus_rows


def identity(version, checksum, candidate):
    return digest(
        canonical(
            [
                POLICY,
                version,
                checksum,
                candidate["key"],
                candidate["origin"],
                candidate["fen"],
                candidate["solution"],
            ]
        )
    )


def bind(row, version, checksum):
    candidate = {**_corpus(row, version), "origin": row["source"]}
    return identity(version, checksum, candidate), candidate


def entries(db, row, version, lower, upper, window, records):
    rows, limited = corpus_rows(db, row["id"], lower, upper, "hangingPiece", 100)
    keys = [bind(item, version, row["checksum"])[0] for item in rows]
    if window is not None and (window.get("keys") != keys or window.get("limited") != limited):
        return None
    selected = select_entries(keys, records)
    return (selected, limited) if selected is not None else None


def select_entries(keys, records):
    if any(records.get(key, {}).get("state") != "complete" for key in keys):
        return None
    return {key: records[key] for key in keys}
