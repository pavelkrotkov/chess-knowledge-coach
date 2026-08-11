"""Deterministic tactical motif opportunities with versioned source facts."""

from __future__ import annotations

import json
from typing import Any

import chess

from .db import Database

DETECTOR_VERSION = "0.1.0"
_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


def _forks(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for attacker in chess.SQUARES:
        piece = board.piece_at(attacker)
        if piece is None:
            continue
        targets = [
            square
            for square in board.attacks(attacker)
            if (target := board.piece_at(square)) is not None
            and target.color != piece.color
            and _VALUES[target.piece_type] >= 3
        ]
        if len(targets) >= 2:
            facts.append(
                {
                    "motif": "fork",
                    "attacker": chess.square_name(attacker),
                    "targets": sorted(chess.square_name(square) for square in targets),
                }
            )
    return facts


def _hanging(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not piece.color, square)
        defenders = board.attackers(piece.color, square)
        if attackers and not defenders:
            facts.append({"motif": "hanging_piece", "square": chess.square_name(square)})
    return facts


def _pins(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for color in chess.COLORS:
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is not None and piece.color == color and board.is_pinned(color, square):
                facts.append(
                    {
                        "motif": "pin",
                        "square": chess.square_name(square),
                        "side": "white" if color else "black",
                    }
                )
    return facts


def detect_motifs(
    board: chess.Board, *, detector_version: str = DETECTOR_VERSION
) -> list[dict[str, Any]]:
    facts = _forks(board) + _hanging(board) + _pins(board)
    for fact in facts:
        fact["detector_version"] = detector_version
        fact["position_fen"] = board.fen()
    return facts


def record_motif_opportunities(
    db: Database,
    position_id: int,
    *,
    detector_version: str = DETECTOR_VERSION,
    outcome: str = "ambiguous",
) -> int:
    """Persist raw motif facts and evidence without inferring human cognition."""
    position = db.connection.execute(
        "SELECT fen FROM positions WHERE id = ?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError(f"unknown position id: {position_id}")
    if outcome not in {"success", "failure", "ambiguous"}:
        raise ValueError("outcome must be success, failure, or ambiguous")
    facts = detect_motifs(chess.Board(position["fen"]), detector_version=detector_version)
    for fact in facts:
        db.connection.execute(
            "INSERT INTO detector_facts(position_id, detector_version, fact_type, payload_json) VALUES (?, ?, ?, ?)",
            (position_id, detector_version, fact["motif"], json.dumps(fact, sort_keys=True)),
        )
        db.connection.execute(
            """INSERT INTO evidence_mappings
            (position_id, skill, operation, outcome, confidence, source_facts_json, mapper_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                position_id,
                fact["motif"],
                "opportunity",
                outcome,
                1.0,
                json.dumps([fact]),
                detector_version,
            ),
        )
    db.connection.commit()
    return len(facts)
