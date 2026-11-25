"""Read a current immutable public fork certificate without proving on GET."""

import sqlite3

from .fact_fingerprint import canonical, digest
from .opening_context_fork_binding import binding, key
from .opening_public_proof_files import latest
from .tactical_study_path import planning


def lookup(root, subject, item):
    if item["source"] is None:
        return {"status": "unavailable"}
    try:
        directory, _ = planning(root, subject)
        payload = latest(directory, key(item["selection"]))
        if payload is None:
            return {"status": "unmeasured"}
        if payload["binding"] != binding(item) or payload["binding_sha256"] != digest(
            canonical(payload["binding"])
        ):
            return {"status": "stale"}
        return {"status": "prepared", **payload}
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        return {"status": "stale"}


def enrich(root, subject, items):
    for item in items:
        item["public_fork"] = lookup(root, subject, item)
