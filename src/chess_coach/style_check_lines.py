"""Reconstruct source-linked legal checking events in one four-ply line."""

import chess

from .mate_proof_moves import move_view
from .style_check_evasions import evasions
from .style_check_mate import witness


def events(board, line, budget=None):
    replay = board.copy()
    root_in_check = board.is_check()
    checks = []
    conditional = None
    pre_third_check = None
    for ply, uci in enumerate(line["pv"].split()[:4], 1):
        move = chess.Move.from_uci(uci)
        if ply == 3:
            pre_third_check = replay.is_check()
            conditional = (
                {"status": "root_in_check", "moves": []}
                if root_in_check
                else witness(replay, budget)
            )
        if replay.gives_check(move):
            view = {
                **move_view(replay, move),
                "ply": ply,
                "color": "white" if replay.turn == chess.WHITE else "black",
                "response": replay.is_check(),
            }
            replay.push(move)
            checks.append({**view, "evasions": evasions(replay)})
        else:
            replay.push(move)
    return {
        "checks": checks,
        "pre_third_in_check": pre_third_check,
        "conditional_mate": conditional,
    }
