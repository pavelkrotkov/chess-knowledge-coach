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
    if window.get("keys") != keys or window.get("limited") != limited:
        return None
    return select_entries(keys, records)


def select_entries(keys, records):
    if any(records.get(key, {}).get("state") != "complete" for key in keys):
        return None
    return {key: records[key] for key in keys}


def finalize(db, data, building, prior):
    keys = building["keys"] + building["public"]["keys"]
    version, checksum, _, _ = building["scope"]
    current = db.connection.execute(
        "SELECT 1 FROM puzzle_corpora WHERE id=? AND version=? AND checksum=? AND state='ready'",
        (building["corpus_id"], version, checksum),
    ).fetchone()
    if current is None:
        data["prior"] = None
        return False, 0
    data["complete"] = {
        "scope": building["scope"],
        "keys": building["keys"],
        "limited": building["limited"],
        "public": {"owner": building["public"]["owner"], "keys": building["public"]["keys"]},
    }
    entries = {**data["entries"], **prior["entries"]}
    data["entries"] = {key: entries[key] for key in keys}
    data["prior"] = None
    data.pop("overflow", None)
    data.pop("pending_scope", None)
    return False, 0
