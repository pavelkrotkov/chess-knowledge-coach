"""Project a qualified 20+20 dated cohort and its separate boundary game."""


def identity(report):
    if not report or not report["comparable"] or report["historical"]:
        return None
    halves = []
    for name in ("newer", "earlier"):
        ids = tuple(game["game_id"] for game in report[name]["root_game_coverage"])
        if len(ids) != 20:
            return None
        halves.append(ids)
    boundary = report["boundary_id"]
    if boundary is None:
        return None
    return (*halves, boundary)
