"""Read opening rows and validate their move sequences."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import chess
import chess.pgn


def _rows(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
            rows = payload if isinstance(payload, list) else payload["openings"]
        else:
            rows = list(csv.DictReader(io.StringIO(text), dialect="excel-tab"))
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"failed to read opening dataset {path}: {exc}") from exc
    if not isinstance(rows, list):
        raise ValueError(f"opening dataset {path} must contain a list of rows")
    return rows


def _moves(row: dict[str, str]) -> list[chess.Move]:
    text = row.get("moves") or row.get("pgn")
    if not text:
        raise ValueError("opening row requires a moves or pgn field")
    if row.get("pgn"):
        game = chess.pgn.read_game(io.StringIO(text))
        if game is None:
            raise ValueError("opening row contains an empty PGN")
        if game.errors:
            raise ValueError(
                f"opening row contains an invalid PGN ({len(game.errors)} parse error(s))"
            )
        return [node.move for node in game.mainline()]
    board = chess.Board()
    moves = []
    for token in text.split():
        moves.append(board.parse_san(token))
        board.push(moves[-1])
    return moves
