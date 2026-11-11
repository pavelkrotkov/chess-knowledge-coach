"""Freeze the broad, versioned cohort of a certified unfamiliar fork."""

import chess

from .fork_contract import VERSION as FORK_VERSION
from .fork_targets import targets
from .objective_fork_contract import VERIFIER
from .objective_fork_snapshot import _anchor
from .related_capture_assessment import HISTORY
from .related_fork import VERSION as RANK_VERSION
from .related_fork_assessment import VERSION
from .related_fork_features import corpus_fork_features

CONTEXT_VERSION = "fork-comparison-context-v1"


def _anchor_role(prompt, solution):
    board = chess.Board(prompt)
    move = board.parse_uci(solution.split()[1])
    _, squares = targets(board, move)
    square = _anchor(board, [chess.square_name(value) for value in squares])
    return board.piece_type_at(chess.parse_square(square))


def context(db, version, key):
    row = db.connection.execute(
        """SELECT p.fen,p.solution,p.rating,p.rating_deviation,c.checksum
        FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state=? AND p.puzzle_id=?""",
        (version, "ready", key),
    ).fetchone()
    if row is None:
        raise ValueError("fork comparison context unavailable")
    rating, deviation = row["rating"], row["rating_deviation"]
    if not all(type(x) is int and 0 <= x < 4000 for x in (rating, deviation)):
        raise ValueError("fork comparison context unavailable")
    prompt, features = corpus_fork_features(row["fen"], row["solution"])
    if not features or features["mover"] != 2 or not row["checksum"]:
        raise ValueError("fork comparison context unavailable")
    return {
        "version": CONTEXT_VERSION,
        "corpus": version,
        "checksum": row["checksum"],
        "cue": RANK_VERSION,
        "assessment": VERSION,
        "proof": VERIFIER,
        "fork": FORK_VERSION,
        "history": HISTORY,
        "attacker": features["mover"],
        "anchor": _anchor_role(prompt, row["solution"]),
        "targets": list(features["target"]),
        "phase": features["phase"],
        "rating_band": rating // 200,
        "deviation_band": deviation // 100,
    }
