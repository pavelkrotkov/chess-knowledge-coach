"""Bind source-specific bad and defended moves to their original piece squares."""

import chess

from .fork_defense_safety import quiet_after


def binding(board, evidence, payload):
    proof = payload["proof"]
    played = board.parse_uci(evidence["context"]["played_move"])
    alternative = board.parse_uci(payload["alternative"]["move"])
    if played not in board.legal_moves or alternative not in board.legal_moves:
        raise ValueError("pin prevention move unavailable")
    bad, good = (played, alternative) if payload["outcome"] == "failure" else (alternative, played)
    if proof.get("mode") in {"exposure", "pinned_capture"}:
        return _existing(board, proof, bad, good)
    return _created(board, proof, bad, good)


def _existing(board, proof, bad, good):
    if proof["type"] not in {"absolute_pin", "relative_pin"}:
        raise ValueError("pin prevention type unavailable")
    return {
        "origin": "existing",
        "attacker": proof["pinner"],
        "pinned": proof["pinned"],
        "rear": proof["rear"],
        "kind": proof["type"],
        "bad": bad.uci(),
        "good": good.uci(),
    }


def _created(board, proof, bad, good):
    after = quiet_after(board, bad)
    if after is None:
        raise ValueError("created pin root unsupported")
    threat = after.parse_uci(proof["move"])
    if threat not in after.legal_moves or proof["pinner"] != chess.square_name(threat.to_square):
        raise ValueError("created pin threat unavailable")
    return {
        "origin": "created",
        "attacker": chess.square_name(threat.from_square),
        "pinned": _before(bad, proof["pinned"]),
        "rear": _before(bad, proof["rear"]),
        "kind": proof["type"],
        "bad": bad.uci(),
        "good": good.uci(),
    }


def _before(move, square):
    return (
        chess.square_name(move.from_square)
        if square == chess.square_name(move.to_square)
        else square
    )
