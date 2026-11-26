"""Publish a completed window while retaining bounded reusable proofs."""

from .capture_corpus_storage import LIMIT


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
    previous = data.get("complete") or {}
    protected = keys + previous.get("keys", []) + (previous.get("public") or {}).get("keys", [])
    entries = {**data["entries"], **prior["entries"]}
    retained = list(dict.fromkeys([*protected, *sorted(entries)]))
    if len(set(protected)) > LIMIT or any(key not in entries for key in protected):
        data["pending_scope"] = building["scope"]
        data["prior"] = None
        return False, 0
    data["complete"] = {
        "scope": building["scope"],
        "keys": building["keys"],
        "limited": building["limited"],
        "public": {"owner": building["public"]["owner"], "keys": building["public"]["keys"]},
    }
    data["entries"] = {key: entries[key] for key in retained[:LIMIT]}
    data["prior"] = None
    data.pop("overflow", None)
    data.pop("pending_scope", None)
    return False, 0
