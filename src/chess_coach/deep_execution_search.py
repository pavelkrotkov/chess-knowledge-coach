"""Run two bounded searches and spool only validated native line fields."""

import json

import chess.engine

from .analysis_comparison import comparison_line
from .deep_execution_lines import alternatives as extract_alternatives
from .deep_execution_lines import first, line, problem
from .deep_execution_uci import analyse, forced
from .deep_execution_work import shared_work


def search(engine, board, position, config, spool):
    limit = chess.engine.Limit(nodes=config["nodes"], time=config["time_limit"])
    required = min(config["multipv"], board.legal_moves.count())
    best_raw, best_error = analyse(engine, board, limit, required)
    played_raw, played_error = (
        ([], best_error) if best_error else forced(engine, board, position, limit)
    )
    alternatives, bad = extract_alternatives(position, board, best_raw)
    best = first(alternatives, position, board)
    played, played_bad = line(position, board, "played", played_raw[0] if played_raw else {})
    if played is None:
        played = comparison_line(position, board, "played", {})
    result = {
        "best": best,
        "played": played,
        "alternatives": alternatives,
        "best_work": shared_work(best_raw),
        "played_work": shared_work(played_raw),
        "required_alternatives": required,
        "problem": problem(best_error, played_error, bad, played_bad),
        "engine_broken": bool(best_error or played_error),
    }
    json.dump(result, spool, allow_nan=False)
    spool.write("\n")
    spool.seek(0)
    return json.load(spool)
