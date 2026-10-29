"""Record bounded legal pawn captures and immediate pawn recaptures."""

from itertools import pairwise

import chess

from .style_center_capture import capture


def _exchanges(captures):
    result = []
    for first, second in pairwise(captures):
        if (
            second["ply"] == first["ply"] + 1
            and first["to"] == second["captured"]
            and first["color"] != second["color"]
            and (first["central"] or second["central"])
        ):
            result.append({"first": first, "recapture": second})
    return result


def events(board, line):
    replay = board.copy()
    captures = []
    for ply, uci in enumerate(line["pv"].split()[:4], 1):
        move = chess.Move.from_uci(uci)
        item = capture(replay, move, ply)
        if item:
            captures.append(item)
        replay.push(move)
    return {
        "captures": [item for item in captures if item["central"]],
        "exchanges": _exchanges(captures),
    }
