"""Prepare bounded public recorded-capture results for both selected branches."""

import json
import sqlite3
import time

from .opening_profile_lookup import _validate, guard
from .opening_public_proof_coverage import branch, unavailable


def branches(index, binding, start, deadline, *, capture_pv=False, engine=None):
    connection = sqlite3.connect(index[0].as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(connection, deadline)
        metadata = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata, transform=index[2], source_metadata=index[3])
        result = {}
        for label in ("played", "alternative"):
            if capture_pv:
                from .opening_public_capture_pv import branch as capture_branch
                from .opening_public_capture_pv import unavailable as capture_unavailable

                cutoff = min(deadline, start + 10) if label == "played" else deadline
                guard(connection, cutoff)
                try:
                    result[label] = capture_branch(
                        connection, binding, binding["source"][label], engine, cutoff
                    )
                except TimeoutError:
                    result[label] = capture_unavailable()
            elif time.monotonic() >= deadline:
                result[label] = unavailable()
            else:
                result[label] = branch(
                    connection, binding, binding["source"][label], start, deadline
                )
        return result, metadata["coverage"]
    finally:
        connection.close()
