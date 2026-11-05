"""Certify an unfamiliar corpus capture with reset game history."""

import time

import chess

from .fact_fingerprint import canonical, digest
from .objective_capture_judge import VERSION as PROOF_VERSION
from .objective_capture_judge import judge
from .puzzle_session_validate import CORPUS_PLIES_LIMIT, solution_moves, validate_line

VERSION = "related-capture-assessment-v1"
HISTORY = "zeroing_setup"
SECONDS = 1.5


def setup(db, version, key):
    row = db.connection.execute(
        """SELECT p.fen,p.solution,c.checksum FROM puzzles p JOIN puzzle_corpora c
        ON c.id=p.corpus_id WHERE c.version=? AND p.puzzle_id=? AND c.state='ready'""",
        (version, key),
    ).fetchone()
    if row is None:
        raise ValueError("capture assessment unavailable")
    moves = solution_moves(row["solution"])
    if len(moves) > CORPUS_PLIES_LIMIT:
        raise ValueError("capture assessment line exceeds the supported bound")
    prompt = validate_line(row["fen"], row["solution"])
    board = chess.Board(row["fen"])
    setup_move = board.parse_uci(moves[0])
    if not board.is_zeroing(setup_move):
        raise ValueError("capture assessment history unavailable")
    board.push(setup_move)
    if board.fen() != prompt:
        raise ValueError("capture assessment prompt changed")
    fingerprint = digest(canonical([version, key, row["fen"], row["solution"], row["checksum"]]))
    return board, moves, fingerprint


def certificate(db, version, key):
    board, moves, fingerprint = setup(db, version, key)
    move = board.parse_uci(moves[1])
    result = judge(
        board,
        move,
        "capture_named_target",
        move.to_square,
        3,
        time.monotonic,
        time.monotonic(),
        SECONDS,
        {},
    )
    if result["status"] != "correct":
        raise ValueError("capture assessment proof unavailable")
    return {
        "version": VERSION,
        "proof_version": PROOF_VERSION,
        "history_mode": HISTORY,
        "source_fingerprint": fingerprint,
        "target": chess.square_name(move.to_square),
        "gain_threshold": 3,
        "proof": result,
    }
