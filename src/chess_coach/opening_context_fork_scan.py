"""Replay one verified public branch and account for a bounded fork search."""

import sqlite3
import time

from .opening_profile_lookup import guard
from .opening_public_fork_scan import scan
from .opening_public_proof_history import positions
from .opening_public_proof_replay import _attribution


def _replay(connection, identity, deadline):
    source, selection = identity["source"], identity["selection"]
    row = connection.execute(
        "SELECT id,total_plies,context FROM games WHERE id=?", (source["record"],)
    ).fetchone()
    if row is None:
        raise ValueError("public record unavailable")
    decision = {
        "ply": source["history"]["ply"],
        "source": {"parent": selection["parent"]},
        "color": selection["color"],
    }
    rows, found, censored, safe = positions(
        connection, row[0], row[1], decision, selection["move"], deadline, all_moves=True
    )
    candidates = [candidate for candidate in found if candidate[0] > decision["ply"]]
    return row, rows, candidates, censored, safe


def evaluate(index, identity, deadline):
    connection = sqlite3.connect(index.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    budget = {"proofs": 0}
    try:
        guard(connection, deadline)
        row, rows, candidates, censored, safe = _replay(connection, identity, deadline)
        if not safe:
            return {"status": "unsupported", "reason": "history_or_draw_unsupported"}
        result = scan(candidates, rows, budget, deadline, material_example=True)
        if result["example"] is not None:
            _attribution(
                connection,
                row[0],
                row[2],
                {
                    "reference": identity["source"],
                    "index_sha256": identity["source"]["index_sha256"],
                },
                result["example"],
            )
        return {
            "status": "checked",
            "selected": 1,
            "positions": len(candidates),
            "censored": censored,
            "interrupted": False,
            "proofs": budget["proofs"],
            "result": result,
        }
    except (TimeoutError, sqlite3.OperationalError):
        if time.monotonic() < deadline:
            raise
        return {"status": "interrupted", "interrupted": True, "proofs": budget["proofs"]}
    finally:
        connection.close()
