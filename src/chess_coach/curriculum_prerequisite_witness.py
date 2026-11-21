"""Replay a stored back-rank witness without running a new solver."""

from .back_rank_terminal import terminal
from .related_backrank_defense_source import _witness


def select_witness(board, defense, outcome, check):
    origin, kind = defense.get("origin"), defense.get("outcome")
    if defense.get("status") != "opportunity" or origin not in {
        "anchored_preexisting",
        "newly_allowed",
    }:
        return None
    if (kind, outcome) == ("allows", "failure"):
        witness = _witness(defense, board)
        return witness if _qualified(board, witness, origin) else None
    if (kind, outcome, origin) != ("avoids", "success", "anchored_preexisting"):
        return None
    return _avoided(board, defense, check)


def _avoided(board, defense, check):
    for witness in defense["anchors"]:
        check()
        if witness["alternative"]["uci"] != defense["played"] and _qualified(
            board, witness, "anchored_preexisting"
        ):
            return witness
    return None


def _legal_witness(board, witness):
    replay = board.copy(stack=True)
    first, mate = witness["alternative"], witness["mate"]
    move = replay.parse_uci(first["uci"])
    if replay.san(move) != first["san"]:
        return False
    replay.push(move)
    move = replay.parse_uci(mate["move"]["uci"])
    if replay.san(move) != mate["move"]["san"]:
        return False
    replay.push(move)
    return terminal(replay) == mate["geometry"]


def _qualified(board, witness, origin):
    if not _legal_witness(board, witness):
        return False
    prior = _prior_mate(board, witness["mate"]["move"]["uci"])
    return prior is not None and prior == (origin == "anchored_preexisting")


def _prior_mate(board, move_text):
    # The existing origin policy compares one legal pre-move candidate.
    if board.is_check() or board.ep_square is not None or board.is_repetition(2):
        return None
    probe = board.copy(stack=False)
    probe.turn = not probe.turn
    if not probe.is_valid() or probe.is_check():
        return None
    try:
        move = probe.parse_uci(move_text)
    except ValueError:
        return False
    probe.push(move)
    return terminal(probe) is not None
