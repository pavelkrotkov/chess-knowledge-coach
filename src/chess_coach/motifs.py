"""Deterministic tactical motif opportunities with versioned source facts."""

from __future__ import annotations

import json
from typing import Any

import chess

from .db import Database

DETECTOR_VERSION = "0.1.0"
MAPPER_VERSION = "0.1.0"
_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


def _legal_targets(board: chess.Board, attacker: chess.Square) -> list[chess.Square]:
    return [
        move.to_square
        for move in board.legal_moves
        if move.from_square == attacker and board.piece_at(move.to_square) is not None
    ]


def _forks(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for attacker in chess.SQUARES:
        piece = board.piece_at(attacker)
        if piece is None or piece.color != board.turn:
            continue
        targets = [
            square
            for square in _legal_targets(board, attacker)
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
        attackers = board.attackers(board.turn, square)
        defenders = board.attackers(piece.color, square)
        if attackers and piece.color != board.turn and not defenders:
            facts.append({"motif": "hanging_piece", "square": chess.square_name(square)})
    return facts


def _pins(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None and piece.color != board.turn and board.is_pinned(piece.color, square):
            facts.append({"motif": "absolute_pin", "square": chess.square_name(square)})
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
    mapper_version: str = MAPPER_VERSION,
    operation: str = "prevent",
    outcome: str = "ambiguous",
    outcomes: dict[str, str] | None = None,
) -> int:
    """Persist raw motif facts and per-fact evidence without inferring cognition."""
    if outcome not in {"success", "failure", "ambiguous"}:
        raise ValueError("outcome must be success, failure, or ambiguous")
    if not operation:
        raise ValueError("operation must not be empty")
    position = db.connection.execute(
        "SELECT p.fen, g.variant FROM positions p JOIN games g ON g.id = p.game_id WHERE p.id = ?",
        (position_id,),
    ).fetchone()
    if position is None:
        raise ValueError(f"unknown position id: {position_id}")
    if position["variant"] != "Standard":
        raise ValueError(f"motif detection does not support variant {position['variant']!r}")
    facts = detect_motifs(chess.Board(position["fen"]), detector_version=detector_version)
    db.connection.execute(
        "DELETE FROM detector_facts WHERE position_id = ? AND detector_version = ?",
        (position_id, detector_version),
    )
    db.connection.execute(
        "DELETE FROM evidence_mappings WHERE position_id = ? AND mapper_version = ? AND operation = ?",
        (position_id, mapper_version, operation),
    )
    for index, fact in enumerate(facts):
        fact_outcome = (outcomes or {}).get(str(index), outcome if len(facts) == 1 else "ambiguous")
        if fact_outcome not in {"success", "failure", "ambiguous"}:
            raise ValueError("all outcomes must be success, failure, or ambiguous")
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
                operation,
                fact_outcome,
                1.0,
                json.dumps([fact]),
                mapper_version,
            ),
        )
    db.connection.commit()
    return len(facts)
