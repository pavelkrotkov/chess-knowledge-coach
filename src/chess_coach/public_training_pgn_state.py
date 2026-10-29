"""Track strict PGN token boundaries and variation structure."""

import chess.pgn

from .public_training_pgn_variation import accept_variation


def accept_token(match, text, state):
    kind = match.lastgroup
    if kind == "tag":
        return (
            not state["started"]
            and chess.pgn.TAG_REGEX.fullmatch(match.group().strip()) is not None
        )
    if kind in {"space", "comment"}:
        return True
    state["started"] = True
    if state["result"]:
        return False
    if kind == "san":
        return _move(match, text, state)
    if kind in {"open", "close"}:
        return accept_variation(kind, state)
    if kind == "result":
        return _result(state)
    return True


def _move(match, text, state):
    if match.end() < len(text) and text[match.end()] not in " \t\r\n{}();$!?":
        return False
    state["moves"][-1] += 1
    return True


def _result(state):
    if len(state["moves"]) != 1:
        return False
    state["result"] = True
    return True
