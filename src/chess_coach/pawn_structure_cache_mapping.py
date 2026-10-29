"""Check active mapping content and links for a cached lesson."""

import json

from .fact_fingerprint import digest
from .mapping_inputs import mapping_batch
from .pawn_structure_cache_checks import content_matches, mapped_matches
from .pawn_structure_cache_items import items
from .pawn_structure_lesson import VERSION
from .pawn_structure_mapping import MAPPER


def _mapping(db, position_id, subject):
    return db.connection.execute(
        """SELECT * FROM mapping_runs WHERE position_id=? AND producer=? AND subject=?
        AND operation='evaluate' AND scope_key='pawn-structure-lesson' AND status='active'""",
        (position_id, MAPPER, subject),
    ).fetchone()


def valid(db, position_id, context, game_id, detector_run, inputs, facts, payloads):
    row = _mapping(db, position_id, context["subject"])
    if (
        row is None
        or row["mapper_version"] != VERSION
        or digest(row["input_json"]) != row["input_hash"]
    ):
        return False
    try:
        data = json.loads(row["input_json"])
        data.pop("reactivation", None)
        if not content_matches(data, inputs, detector_run, payloads, context, game_id):
            return False
        mapped = items(db, row, facts)
        if not mapped_matches(mapped, data["context"]):
            return False
        return mapping_batch(mapped)[1] == row["output_hash"]
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False
