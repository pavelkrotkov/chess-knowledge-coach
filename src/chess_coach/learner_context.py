"""Create decision context without attributing opponent moves to the learner."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from chess import Board

from .analysis_positions import decisions
from .db import Database
from .learner_identity import learner_color, normalize_identity
from .learner_time import observation_time


def decision_context_boards(
    db: Database, game_id: int, *, learner: str | None
) -> Iterator[tuple[dict[str, object], Board]]:
    game = db.connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    color = learner_color(game, learner)
    subject = normalize_identity(learner) if color is not None else None
    observed = observation_time(game["pgn"])
    processed = datetime.now(UTC).isoformat()
    clocks: dict[str, float | None] = {"white": None, "black": None}
    for position, board in decisions(db.connection, game):
        mover = "white" if board.turn else "black"
        other = "black" if mover == "white" else "white"
        before = clocks[mover]
        after = position["clock_seconds"]
        clocks[mover] = after
        context = {
            "subject": subject if mover == color else None,
            "learner_color": color,
            "game_id": game["id"],
            "source": game["source"],
            "source_id": game["source_id"],
            "position_id": position["id"],
            "ply": position["ply"],
            "pre_move_fen": board.fen(),
            "mover": mover,
            "mover_name": game[mover],
            "played_move": position["uci"],
            "observation_at": observed,
            "observation_precision": "game_start" if observed else None,
            "processed_at": processed,
            "clock_before_seconds": before,
            "clock_after_seconds": after,
            "time_control": game["time_control"],
            "mover_rating": game[f"{mover}_elo"],
            "other_rating": game[f"{other}_elo"],
        }
        yield context, board


def decision_contexts(
    db: Database, game_id: int, *, learner: str | None
) -> Iterator[dict[str, object]]:
    for context, _board in decision_context_boards(db, game_id, learner=learner):
        yield context
