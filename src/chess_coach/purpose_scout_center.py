"""Retain only usable ranked scout nominations from the restricted root set."""

from .decision_line_view import view_line
from .purpose_config import SCOUT_NODES
from .purpose_iteration_line import structural
from .purpose_lines import roots, work


def choose(board, position, candidates, raw, error, items, invalid):
    allowed = {move.uci() for move in candidates}
    usable = [item for item in items if valid(item, board, position, allowed)]
    result = {"lines": usable, "work": work(raw, SCOUT_NODES)}
    if error:
        return result, None, error
    if not usable:
        return result, None, "invalid_scout" if invalid else "no_distinct_nominee"
    if not distinct(usable):
        return result, None, "invalid_scout"
    return result, roots(usable)[0], None


def distinct(items):
    return len(items) <= 2 and len(set(roots(items))) == len(items)


# The scout needs a real ranked line, but not a four-ply final comparison.
def valid(item, board, position, allowed):
    try:
        line = item["line"]
        if type(item["rank"]) is not int or item["rank"] not in (1, 2):
            return False
        if line["position_id"] != position["id"] or line["role"] != "candidate":
            return False
        if line["root_move"] not in allowed or not structural(line, allow_bound=True):
            return False
        return view_line(line, board, position["uci"])["status"] == "limited"
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return False
