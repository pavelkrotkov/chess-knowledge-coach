"""Read exact, context-matched branches from the reviewed recent reference."""

import json
import sqlite3
import time

from .opening_fit_later_index import locate
from .opening_profile_lookup import _validate, guard
from .opening_profile_metadata import summarize_profile
from .opening_profile_queens import summarize as queen_summary
from .opening_recent_select import rows as select_rows


def profile(root, subject, decision, move, control, deadline):
    index = locate(root, subject, "recent")
    connection = sqlite3.connect(index[0].as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(connection, deadline)
        metadata = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(metadata, transform=index[2], source_metadata=index[3])
        parent, ply = decision["catalog"]["parent"], decision["ply"]
        rows, context = select_rows(connection, parent, move, ply, control)
        selected = [(row[0], ply) for row in rows[:10]]
        summary = summarize_profile(connection, selected, parent, move, True)
        summary["queens"] = queen_summary(connection, rows[:10], decision, move, deadline)
        result = {
            **summary,
            **context,
            "more_matches": len(rows) > 10,
            "coverage": metadata["coverage"],
            "source": metadata["source_archive"],
            "license": metadata["license"],
            "license_url": metadata["license_url"],
            "source_sha256": metadata["source_sha256"],
            "source_metadata": index[3],
            "reference": "recent",
            "decision_ply": ply,
            "control": control,
        }
    finally:
        connection.close()
    if time.monotonic() >= deadline:
        raise TimeoutError("opening profile deadline")
    if locate(root, subject, "recent") != index:
        raise ValueError("recent reference changed")
    if time.monotonic() >= deadline:
        raise TimeoutError("opening profile deadline")
    return result
