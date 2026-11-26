"""Rebind prepared corpus windows to their current immutable rows."""

from .capture_corpus_coverage import entries
from .capture_corpus_coverage import identity as identity
from .capture_corpus_storage import POLICY as POLICY
from .capture_corpus_storage import load as load
from .capture_corpus_storage import location as location
from .fact_fingerprint import canonical, digest


def complete(db, root, version, lower, upper):
    data = load(db, root)
    window = data.get("complete") if data else None
    row = db.connection.execute(
        "SELECT id,checksum FROM puzzle_corpora WHERE version=? AND state=?", (version, "ready")
    ).fetchone()
    if row is None or not isinstance(window, dict):
        return None
    if window.get("scope") != [version, row["checksum"], lower, upper]:
        return None
    selected = entries(db, row, version, lower, upper, window, data["entries"])
    if selected is None:
        return None
    return {
        "binding": data["policy"],
        "scope": window["scope"],
        "limited": window["limited"],
        "entries": selected,
    }


def observation(db, root, version, lower, upper):
    window = complete(db, root, version, lower, upper)
    return digest(canonical([POLICY, window]))
