"""Verify mapping run scope and immutable consumed source context."""

import json

from .pawn_coach_contract import MAPPER, SCOPE, VERSION
from .pawn_coach_mapping import mapping_context


def valid_mapping(db, evidence, fact, prepared):
    row = db.connection.execute(
        """SELECT input_json FROM mapping_runs WHERE id=? AND producer=? AND mapper_version=?
        AND scope_key=? AND status='active' AND position_id=? AND subject=? AND operation=?""",
        (
            evidence["mapping_run_id"],
            MAPPER,
            VERSION,
            SCOPE,
            evidence["position_id"],
            evidence["subject"],
            evidence["operation"],
        ),
    ).fetchone()
    if row is None:
        return False
    expected = {
        "source": prepared["inputs"],
        "fact_run": fact["detector_run_id"],
        "context": mapping_context(prepared),
    }
    try:
        return json.loads(row["input_json"]) == expected
    except (TypeError, ValueError):
        return False
