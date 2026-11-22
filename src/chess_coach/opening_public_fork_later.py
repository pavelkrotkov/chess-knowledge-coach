"""Select and replay one later fork window from the verified full index."""

import json
import sqlite3
import time

from .opening_full_history_build import TRANSFORM
from .opening_full_history_locate import locate
from .opening_profile_lookup import _validate, guard
from .opening_public_fork_later_coverage import branch, unavailable
from .opening_public_proof_index import index_hash
from .opening_recent_index import metadata as source_metadata


def bound(root, subject, deadline):
    index = locate(root, subject)
    sha = index_hash(index[0], deadline)
    if locate(root, subject) != index:
        raise ValueError("full history reference changed")
    return index, sha


def branches(index, binding, deadline):
    connection = sqlite3.connect(index[0].as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(connection, deadline)
        values = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(values, transform=TRANSFORM, source_metadata=source_metadata(index[3]))
        results = {}
        for label in ("played", "alternative"):
            results[label] = (
                unavailable("deadline")
                if time.monotonic() >= deadline
                else branch(connection, binding, binding["source"][label], deadline)
            )
        return results, values["coverage"]
    finally:
        connection.close()
