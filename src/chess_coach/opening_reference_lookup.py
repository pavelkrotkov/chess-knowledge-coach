"""Look up bounded precomputed matches in an independent reference index."""

import json
import sqlite3
from pathlib import Path

from .opening_reference_source import LICENSE, LICENSE_URL, SOURCE, SOURCE_SHA256
from .opening_reference_url import site as valid_site
from .opening_snapshot import GRAPH_SHA256, VERSION


def lookup(path: Path, key):
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        metadata = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata")}
        if (
            metadata.get("source_sha256"),
            metadata.get("opening_graph"),
            metadata.get("opening_version"),
        ) != (SOURCE_SHA256, GRAPH_SHA256, VERSION):
            return None
        rows = db.execute(
            """SELECT games.id,context,site,san FROM positions JOIN games ON games.id=positions.game_id
                          WHERE positions.key=? ORDER BY games.id LIMIT 3""",
            (key,),
        ).fetchall()
        return {
            "coverage": metadata["coverage"],
            "source": SOURCE,
            "source_sha256": SOURCE_SHA256,
            "license": LICENSE,
            "license_url": LICENSE_URL,
            "items": [
                {
                    "number": row[0],
                    "context": json.loads(row[1]),
                    "site": valid_site(row[2]),
                    "san": row[3],
                }
                for row in rows
            ],
        }
    finally:
        db.close()
