"""Run UCI calls with sanitized failure states."""


def analyse(engine, board, limit, multipv, root_moves=None):
    try:
        result = engine.analyse(board, limit, multipv=multipv, root_moves=root_moves)
        return (
            [dict(item) for item in result] if isinstance(result, list) else [dict(result)]
        ), None
    except TimeoutError:
        return [], "engine_timeout"
    except Exception:
        return [], "engine_failure"


def forced(engine, board, position, limit):
    move = board.parse_uci(position["uci"])
    return analyse(engine, board, limit, 1, [move])
