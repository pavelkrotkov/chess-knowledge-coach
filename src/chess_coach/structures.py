"""Deterministic atomic board-structure detectors and episode extraction."""

from __future__ import annotations

import json
from typing import Any, cast

import chess

from .db import Database

DETECTOR_VERSION = "0.1.0"
_FILES = "abcdefgh"


def _pawns(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    return list(board.pieces(chess.PAWN, color))


def _file(square: chess.Square) -> int:
    return chess.square_file(square)


def _rank(square: chess.Square) -> int:
    return chess.square_rank(square)


def _square_name(square: chess.Square) -> str:
    return chess.square_name(square)


def _pawn_files(board: chess.Board, color: chess.Color) -> set[int]:
    return {_file(square) for square in _pawns(board, color)}


def _isolated(board: chess.Board, color: chess.Color) -> list[str]:
    files = _pawn_files(board, color)
    return sorted(
        _square_name(square)
        for square in _pawns(board, color)
        if _file(square) - 1 not in files and _file(square) + 1 not in files
    )


def _open_files(board: chess.Board) -> list[str]:
    return [
        _FILES[file_index]
        for file_index in range(8)
        if not any(_file(square) == file_index for square in board.pieces(chess.PAWN, chess.WHITE))
        and not any(_file(square) == file_index for square in board.pieces(chess.PAWN, chess.BLACK))
    ]


def _half_open_files(board: chess.Board, color: chess.Color) -> list[str]:
    own = _pawn_files(board, color)
    enemy = _pawn_files(board, not color)
    return [_FILES[index] for index in range(8) if index not in own and index in enemy]


def _backward(board: chess.Board, color: chess.Color) -> list[str]:
    pawns = _pawns(board, color)
    result = []
    direction = 1 if color == chess.WHITE else -1
    for square in pawns:
        file_index = _file(square)
        rank_index = _rank(square)
        neighbors = [
            other
            for other in pawns
            if abs(_file(other) - file_index) == 1 and (_rank(other) - rank_index) * direction > 0
        ]
        forward = (
            chess.square(file_index, rank_index + direction)
            if 0 <= rank_index + direction < 8
            else None
        )
        if neighbors and forward is not None and board.attackers(not color, forward):
            result.append(_square_name(square))
    return sorted(result)


def _hanging(board: chess.Board, color: chess.Color) -> list[str]:
    pawns = _pawns(board, color)
    result = []
    for square in pawns:
        for other in pawns:
            if _file(other) == _file(square) + 1 and _rank(other) == _rank(square):
                adjacent_files = {_file(square) - 1, _file(other) + 1}
                supported = any(_file(pawn) in adjacent_files for pawn in pawns)
                if not supported:
                    result.extend([_square_name(square), _square_name(other)])
    return sorted(set(result))


def _minority(board: chess.Board, color: chess.Color) -> list[str]:
    enemy = not color
    result = []
    for name, files in (("queenside", range(4)), ("kingside", range(4, 8))):
        own_count = sum(_file(square) in files for square in _pawns(board, color))
        enemy_count = sum(_file(square) in files for square in _pawns(board, enemy))
        if own_count < enemy_count:
            result.append(name)
    return result


def _space(board: chess.Board, color: chess.Color) -> int:
    target_ranks = range(4, 8) if color == chess.WHITE else range(0, 4)
    return sum(
        1
        for pawn in _pawns(board, color)
        for target in board.attacks(pawn)
        if _rank(target) in target_ranks
    )


def _locked_center(board: chess.Board) -> bool:
    center = (chess.D4, chess.E4, chess.D5, chess.E5)
    return all(
        board.piece_at(square) == chess.Piece(chess.PAWN, color)
        for square, color in (
            (chess.D4, chess.WHITE),
            (chess.E4, chess.WHITE),
            (chess.D5, chess.BLACK),
            (chess.E5, chess.BLACK),
        )
    ) and all(board.piece_at(square) is not None for square in center)


def extract_features(board: chess.Board) -> dict[str, Any]:
    """Return JSON-compatible deterministic atomic features for a position."""
    return {
        "open_files": _open_files(board),
        "half_open_files": {
            "white": _half_open_files(board, chess.WHITE),
            "black": _half_open_files(board, chess.BLACK),
        },
        "isolated_pawns": {
            "white": _isolated(board, chess.WHITE),
            "black": _isolated(board, chess.BLACK),
        },
        "backward_pawns": {
            "white": _backward(board, chess.WHITE),
            "black": _backward(board, chess.BLACK),
        },
        "hanging_pawns": {
            "white": _hanging(board, chess.WHITE),
            "black": _hanging(board, chess.BLACK),
        },
        "locked_center": _locked_center(board),
        "space": {"white": _space(board, chess.WHITE), "black": _space(board, chess.BLACK)},
        "minority_structure": {
            "white": _minority(board, chess.WHITE),
            "black": _minority(board, chess.BLACK),
        },
    }


def _structure_names(features: dict[str, object]) -> list[str]:
    names = []
    if features["open_files"]:
        names.append("open_files")
    if features["locked_center"]:
        names.append("locked_center")
    isolated = cast(dict[str, list[str]], features["isolated_pawns"])
    hanging = cast(dict[str, list[str]], features["hanging_pawns"])
    if any(isolated.values()):
        names.append("isolated_pawns")
    if any(hanging.values()):
        names.append("hanging_pawns")
    return names


def extract_game_episodes(
    db: Database,
    game_id: int,
    *,
    detector_version: str = DETECTOR_VERSION,
) -> int:
    """Extract contiguous same-feature episodes for a stored Standard game."""
    game = db.connection.execute("SELECT variant FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    if game["variant"] != "Standard":
        raise ValueError(f"structure extraction does not support variant {game['variant']!r}")
    rows = db.connection.execute(
        "SELECT ply, fen FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
    ).fetchall()
    db.connection.execute(
        "DELETE FROM structure_episodes WHERE game_id = ? AND detector_version = ?",
        (game_id, detector_version),
    )
    episodes: list[tuple[int, int, dict[str, object]]] = []
    for row in rows:
        features = extract_features(chess.Board(row["fen"]))
        if episodes and episodes[-1][2] == features and episodes[-1][1] + 1 == row["ply"]:
            episodes[-1] = (episodes[-1][0], row["ply"], features)
        else:
            episodes.append((row["ply"], row["ply"], features))
    for start, end, features in episodes:
        db.connection.execute(
            """INSERT INTO structure_episodes
            (game_id, start_ply, end_ply, features_json, structure_json, confidence, detector_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id,
                start,
                end,
                json.dumps(features, sort_keys=True),
                json.dumps(_structure_names(features)),
                1.0,
                detector_version,
            ),
        )
    db.connection.commit()
    return len(episodes)
