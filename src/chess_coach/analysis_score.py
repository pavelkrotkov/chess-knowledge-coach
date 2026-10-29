"""Keep engine-native score and WDL values in the decision mover's perspective."""

import json


def native_score(board, line):
    score = line.get("score")
    if score is None:
        return None, None, None
    native = score.pov(board.turn)
    if native.is_mate():
        kind, value = "mate", native.mate()
    else:
        kind, value = "cp", native.score()
    return kind, value, _bound(line, score.turn != board.turn)


def _bound(line, reverse):
    lower, upper = bool(line.get("lowerbound")), bool(line.get("upperbound"))
    if lower and upper:
        raise ValueError("engine returned conflicting score bounds")
    if not lower and not upper:
        return "exact"
    return "upper" if lower == reverse else "lower"


def native_wdl(board, line):
    wdl = line.get("wdl")
    if wdl is None:
        return None
    values = wdl.pov(board.turn)
    return json.dumps([values.wins, values.draws, values.losses])
