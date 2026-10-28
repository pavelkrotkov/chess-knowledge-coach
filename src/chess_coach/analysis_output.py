"""Persist scored engine lines for a specific pre-move decision."""

from __future__ import annotations

import sqlite3

import chess


def line_fields(position: sqlite3.Row, board: chess.Board, number: int, line: dict) -> tuple:
    best_move, pv = line_moves(line, board)
    score = line.get("score")
    score_cp = score.pov(board.turn).score(mate_score=100000) if score is not None else None
    return (
        position["id"],
        score_cp,
        best_move,
        position["uci"],
        number,
        pv,
        line.get("nodes"),
        line.get("depth"),
        board.fen(),
        "white" if board.turn else "black",
    )


def save_fields(connection: sqlite3.Connection, run_id: int, fields: list) -> None:
    connection.execute(
        """INSERT INTO engine_outputs
        (run_id, position_id, score_cp, best_move, played_move, multipv, pv, nodes, depth,
         decision_fen, score_pov)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, *fields),
    )


def line_moves(line: dict, board: chess.Board) -> tuple[str | None, str | None]:
    pv = line.get("pv") or []
    if not pv:
        return None, None
    if pv[0] not in board.legal_moves:
        raise ValueError("engine returned an illegal best move")
    return pv[0].uci(), " ".join(move.uci() for move in pv)
