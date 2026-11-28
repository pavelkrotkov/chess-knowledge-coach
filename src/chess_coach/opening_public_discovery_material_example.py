"""Attribute every recorded material certificate to its original public history."""

from functools import partial

import chess

from .discovery_geometry import discoveries
from .discovery_proof import prove
from .fact_fingerprint import canonical, digest
from .objective_short_history import history_hash
from .opening_public_mate_coverage import observation
from .opening_public_mate_policy import check
from .opening_public_proof_replay import _attribution


def certificates(board, proofs):
    values = []
    for proof in proofs:
        value = dict(proof)
        value["slider_piece"] = chess.piece_name(
            board.piece_type_at(chess.parse_square(proof["slider"]))
        )
        value["target_piece"] = chess.piece_name(
            board.piece_type_at(chess.parse_square(proof["target"]))
        )
        values.append(value)
    return values


def example(db, row, binding, source, moves, rows, ply, board, recorded, proofs):
    value = {
        "ply": ply,
        "fen": board.fen(),
        "side_to_move": "white" if board.turn else "black",
        "moving_piece": chess.piece_name(board.piece_type_at(recorded.from_square)),
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "certificates": certificates(board, proofs),
        "source_identity": source,
        "history_hash": history_hash(board),
        "history_sha256": digest(canonical(rows[: ply - 1])),
        "full_history_sha256": digest(canonical(moves)),
    }
    _attribution(db, row[0], row[2], binding, value)
    return value


def scan(db, row, binding, source, moves, rows, candidates, censored, deadline):
    checked = unresolved = 0
    tick = partial(check, deadline)
    for ply, board, recorded in candidates:
        tick()
        checked += 1
        if not discoveries(board, recorded):
            continue
        proofs = [item for item in prove(board, recorded, check=tick) if not item["mate"]]
        if not proofs:
            unresolved += 1
            continue
        value = example(db, row, binding, source, moves, rows, ply, board, recorded, proofs)
        result = observation(censored, example=value, analyzed=True)
        return {
            **result,
            "roots_checked": checked,
            "geometry_unresolved": unresolved,
            "positions_unvisited": len(candidates) - checked,
        }
    result = observation(censored, analyzed=True)
    return {
        **result,
        "roots_checked": checked,
        "geometry_unresolved": unresolved,
        "positions_unvisited": 0,
    }
