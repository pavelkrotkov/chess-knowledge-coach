"""Format bounded contexts for the private chooser."""

import chess

from .opening_context_choice import reason, token


def _path(moves):
    board = chess.Board()
    result = []
    for uci in moves:
        move = board.parse_uci(uci)
        result.append(board.san(move))
        board.push(move)
    return " ".join(result) or "Starting position"


def decorate(report):
    for group in report["contexts"].values():
        for parent in group["parents"]:
            parent["description"] = _path(parent["path"])
            for item in parent["items"]:
                item["choice_token"] = token(item["selection"])
                item["admission"] = reason(report, item)
