"""Reconstruct the scheduled task prompt without trusting its theme."""

import chess

from .curriculum_reference import reference
from .db import Database
from .puzzle_session_validate import legal_move


def referenced_prompt(db: Database, source_ref: str) -> str | None:
    ref = reference(source_ref)
    if ref is None:
        return None
    row = db.connection.execute(
        """SELECT p.fen,p.solution FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND p.puzzle_id=?""",
        ref,
    ).fetchone()
    if row is None:
        return None
    try:
        board = chess.Board(row["fen"])
        if not board.is_valid():
            return None
        board.push(legal_move(board, row["solution"].split(maxsplit=1)[0]))
        return " ".join(board.fen().split()[:4])
    except (ValueError, TypeError, IndexError, AttributeError):
        return None
