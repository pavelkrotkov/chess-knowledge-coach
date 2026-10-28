"""Apply a motif detector and its mappings as one atomic batch."""

import chess

from .db import Database
from .mapping_transaction import mapping_transaction
from .motif_detectors import detect_motifs
from .motif_persist import persist_run


def persist_motifs(
    db: Database,
    position_id: int,
    *,
    detector_version: str,
    mapper_version: str,
    operation: str,
    outcome: str,
    outcomes: dict[str, str] | None,
) -> int:
    if outcome not in {"success", "failure", "ambiguous"}:
        raise ValueError("invalid outcome")
    if not operation:
        raise ValueError("operation must not be empty")
    position = db.connection.execute(
        """SELECT p.fen, g.variant FROM positions p
        JOIN games g ON g.id = p.game_id WHERE p.id = ?""",
        (position_id,),
    ).fetchone()
    if position is None:
        raise ValueError(f"unknown position id: {position_id}")
    if position["variant"] != "Standard":
        raise ValueError(f"motif detection does not support variant {position['variant']!r}")
    facts = detect_motifs(chess.Board(position["fen"]), detector_version=detector_version)
    selected = _outcomes(facts, outcome, outcomes or {})
    with mapping_transaction(db):
        persist_run(db, position_id, detector_version, mapper_version, operation, facts, selected)
    return len(facts)


def _outcomes(facts: list[dict], outcome: str, outcomes: dict[str, str]) -> list[str]:
    selected = [
        outcomes.get(str(i), outcome if len(facts) == 1 else "ambiguous") for i in range(len(facts))
    ]
    if any(value not in {"success", "failure", "ambiguous"} for value in selected):
        raise ValueError("all outcomes must be success, failure, or ambiguous")
    return selected
