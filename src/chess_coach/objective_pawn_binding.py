"""Validate a pawn continuation witness against its immutable request and history."""

import json

from . import pawn_proof, pawn_tables
from .objective_pawn_contract import VERIFIER
from .objective_pawn_interval_binding import correct_root, valid_reply
from .objective_short_history import history_hash


def binding(row, result, board, session):
    fields = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "event_prefix_hash",
        "source_hash",
    )
    if any(result.get(field) != row[field] for field in fields):
        raise ValueError("pawn continuation binding changed")
    data = json.loads(session["provenance_json"])
    bounds = result["continuation"].get("opponent_bounds")
    if not _proof_matches(result, board, data, bounds):
        raise ValueError("pawn continuation proof changed")


def _proof_matches(result, board, data, bounds):
    return not (
        result.get("verifier") != VERIFIER
        or result.get("proof_version") != pawn_proof.VERSION
        or result.get("proof_manifest_sha256") != pawn_tables.MANIFEST_SHA256
        or result.get("history_hash") != history_hash(board)
        or result.get("goal") != data.get("result_goal")
        or not correct_root(result)
        or not valid_reply(bounds, result.get("goal"))
    )
