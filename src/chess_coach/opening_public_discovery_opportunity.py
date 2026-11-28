"""Build one representative opportunity result from original game positions."""

from .opening_public_discovery_material_example import example
from .opening_public_discovery_opportunity_scan import position
from .opening_public_mate_coverage import observation, record


def scan(db, row, binding, source, moves, rows, candidates, censored, deadline):
    checked = unresolved = 0
    for number, (ply, board, recorded) in enumerate(candidates):
        roots, count, unknown, unfinished = position(board, recorded, deadline)
        checked += count
        unresolved += unknown
        if roots or unfinished:
            value = None
            if roots:
                value = example(db, row, binding, source, moves, rows, ply, board, recorded, [])
                value["roots"] = roots
            result = observation(
                censored, example=value, analyzed=bool(checked), incomplete=bool(unfinished)
            )
            return {
                **result,
                "roots_checked": checked,
                "geometry_unresolved": unresolved,
                "positions_unvisited": len(candidates) - number - 1,
                "unfinished_roots": unfinished,
                "interrupted": bool(unfinished),
            }
    result = observation(censored, analyzed=True)
    return {
        **result,
        "roots_checked": checked,
        "geometry_unresolved": unresolved,
        "positions_unvisited": 0,
        "unfinished_roots": 0,
        "interrupted": False,
    }


def record_opportunity(result, item):
    record(result, {**item, "example": None})
    result["unfinished_roots"] += item.get("unfinished_roots", 0)
    if item["example"]:
        result["examples"].append({**item["example"], "interrupted": bool(item.get("interrupted"))})
