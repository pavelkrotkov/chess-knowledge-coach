"""Verify existing and newly added run-to-provenance links."""

import hashlib
import pickle


def link_value(run_id, provenance_id):
    value = pickle.dumps((run_id, provenance_id), protocol=4)
    return int.from_bytes(hashlib.sha256(value).digest(), "big")


def links(connection, deadline):
    """Order-independent fingerprint, allowing newly inserted links to be accounted for."""
    count = total = 0
    for run_id, provenance_id in connection.execute(
        "SELECT run_id,provenance_id FROM analysis_run_provenance ORDER BY run_id"
    ):
        deadline.check()
        count += 1
        total = (total + link_value(run_id, provenance_id)) % (1 << 256)
    return count, total
