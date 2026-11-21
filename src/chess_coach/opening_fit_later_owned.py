"""Recheck branch-specific owned center choices after a later opening decision."""

from .opening_fit_later_group import group
from .opening_fit_owned import GAME_LIMIT, _relevant
from .opening_fit_owned_summary import MIN_GAMES
from .style_report import style_report


def collect(db, learner, decision, moves):
    preliminary, limits = _relevant(db, learner)
    if preliminary["possible_games"] < MIN_GAMES:
        return {"status": "insufficient", "preliminary": preliminary, "limits": limits}
    report = style_report(db, learner, max_games=GAME_LIMIT)
    groups, excluded = group(db, learner, decision, report["early_center"]["observations"], moves)
    if report["coverage"].get("boundary_tie"):
        for summary in groups.values():
            summary["positive"] = False
    return {
        "status": "checked",
        "preliminary": preliminary,
        "scope": report["coverage"],
        "coverage": report["early_center"]["coverage"],
        "branches": groups,
        "excluded": excluded,
        "limits": limits,
    }
