"""Reconstruct each decision from the immutable PGN and verify stored plies."""

from __future__ import annotations

import io
import sqlite3
from collections.abc import Iterator

import chess
import chess.pgn


def decisions(
    connection: sqlite3.Connection, game: sqlite3.Row
) -> Iterator[tuple[sqlite3.Row, chess.Board]]:
    parsed = chess.pgn.read_game(io.StringIO(game["pgn"]))
    if parsed is None or parsed.errors:
        raise ValueError("invalid or incomplete game PGN")
    if game["variant"] != "Standard":
        raise ValueError("analysis supports only Standard chess")
    board = parsed.board()
    rows = connection.execute(
        "SELECT * FROM positions WHERE game_id = ? ORDER BY ply", (game["id"],)
    ).fetchall()
    nodes = list(parsed.mainline())
    if len(rows) != len(nodes):
        raise ValueError("stored positions do not match game PGN")
    for ply, (row, node) in enumerate(zip(rows, nodes, strict=True), start=1):
        before = board.copy()
        verify_ply(board, row, node.move, ply)
        yield row, before


def verify_ply(board: chess.Board, row: sqlite3.Row, move: chess.Move, ply: int) -> None:
    if row["ply"] != ply or row["uci"] != move.uci() or move not in board.legal_moves:
        raise ValueError(f"stored move does not match game PGN at ply {ply}")
    board.push(move)
    if board.fen() != row["fen"]:
        raise ValueError(f"stored position does not match game PGN at ply {ply}")
