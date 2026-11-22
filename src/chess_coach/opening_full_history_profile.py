"""Read bounded late positions for an exact nominal-context public branch."""

import json
import sqlite3
import time

from .opening_full_history_build import TRANSFORM
from .opening_full_history_locate import locate
from .opening_full_history_replay import POLICY
from .opening_full_history_summary import summarize
from .opening_profile_lookup import _validate, guard
from .opening_public_proof_index import index_hash
from .opening_recent_index import metadata
from .opening_recent_select import rows as select_rows


def _read(index, decision, move, control, deadline):
    checksum = index_hash(index[0], deadline)
    db = sqlite3.connect(index[0].as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, deadline)
        values = {
            key: json.loads(value)
            for key, value in db.execute("SELECT key,value FROM metadata LIMIT 32")
        }
        _validate(values, transform=TRANSFORM, source_metadata=metadata(index[3]))
        rows, context = select_rows(
            db, decision["catalog"]["parent"], move, decision["ply"], control
        )
        summary = summarize(db, rows[: POLICY["games_per_branch"]], decision, move, deadline - 0.25)
        return {
            **summary,
            **context,
            "more_matches": len(rows) > POLICY["games_per_branch"],
            "source_sha256": values["source_sha256"],
            "index_sha256": checksum,
            "index_transform": TRANSFORM,
            "coverage": values["coverage"],
            "source_metadata": metadata(index[3]),
            "policy": POLICY,
            "branch_move": move,
            "decision_ply": decision["ply"],
            "control": control,
        }
    finally:
        db.close()


def profile(root, subject, decision, move, control, deadline):
    if control == "unknown":
        return {"status": "unavailable", "reason": "nominal_context_unknown"}
    try:
        index = locate(root, subject)
        result = _read(index, decision, move, control, deadline)
        if time.monotonic() >= deadline or locate(root, subject) != index:
            raise ValueError("full history reference changed")
        return result
    except (OSError, ValueError, TypeError, KeyError, IndexError, sqlite3.Error, TimeoutError):
        return {"status": "unavailable", "reason": "full_history_reference_unavailable"}
