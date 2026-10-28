"""Describe a verified tactical decision without claiming mastery."""

from __future__ import annotations

from typing import Any

from .db import Database

MAPPER_VERSION = "mate-one-preview-1.0.0"


def assess_fact(db: Database, position_id: int, fact: dict[str, Any]) -> dict[str, object]:
    conflicts = _engine_conflicts(db, position_id, fact)
    if conflicts:
        outcome = "ambiguous"
        rationale = "a recorded engine best move disagrees with the immediate legal mates"
    elif fact["played_checkmate"]:
        outcome = "success"
        rationale = "the played legal move immediately checkmates"
    elif fact["played_stalemate"]:
        outcome = "failure"
        rationale = "the played legal move immediately stalemates instead of an available mate"
    else:
        outcome = "ambiguous"
        rationale = "the played legal move does not immediately end the game"
    return {
        "skill": "mate_in_one",
        "operation": "execute",
        "outcome": outcome,
        "confidence_rationale": rationale,
        "engine_conflict_ids": conflicts,
        "mapper_version": MAPPER_VERSION,
        "mapping_status": "preview",
        "human_validated": False,
    }


def _engine_conflicts(db: Database, position_id: int, fact: dict[str, Any]) -> list[int]:
    turn = "white" if fact["pre_move_fen"].split()[1] == "w" else "black"
    rows = db.connection.execute(
        """SELECT id, best_move FROM engine_outputs
        WHERE position_id = ? AND decision_fen = ? AND score_pov = ?
          AND multipv = 1 AND best_move IS NOT NULL ORDER BY id""",
        (position_id, fact["pre_move_fen"], turn),
    ).fetchall()
    return [row["id"] for row in rows if row["best_move"] not in fact["mating_moves"]]
