"""Rebind prepared corpus windows to their current immutable rows."""

from .capture_corpus_coverage import entries
from .capture_corpus_coverage import identity as identity
from .capture_corpus_storage import POLICY as POLICY
from .capture_corpus_storage import load as load
from .capture_corpus_storage import location as location
from .capture_public_window import entries as public_entries
from .fact_fingerprint import canonical, digest


def complete(db, root, version, lower, upper, subject=None, games=None):
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
    public = public_entries(db, subject, window.get("public"), data["entries"], games)
    if selected is None or public is None:
        return None
    return {
        "binding": data["policy"],
        "scope": window["scope"],
        "limited": window["limited"],
        "entries": selected,
        "public": public,
    }


def require(db, root, version, corpus, subject, games):
    window = complete(db, root, version, corpus["lower"], corpus["upper"], subject, games)
    if window is None or digest(canonical(window)) != corpus.get("capture_preparation"):
        raise ValueError("capture preparation changed")
    return window


def observation(db, root, version, lower, upper, subject=None, games=None):
    window = complete(db, root, version, lower, upper, subject, games)
    return digest(canonical([POLICY, window]))
