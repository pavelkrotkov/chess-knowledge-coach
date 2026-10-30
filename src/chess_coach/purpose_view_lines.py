"""Expose only revalidated candidate lines and bounded native work."""

from .purpose_final import grade
from .purpose_lines import viewed
from .purpose_view_binding import matches

FIELDS = ("root_move", "score_kind", "score_value", "score_bound", "depth", "pv", "san", "status")


def final_view(result, board, played, position):
    final = result.get("final")
    if not isinstance(final, dict) or not isinstance(final.get("lines"), list):
        return None
    try:
        if not matches(result, played):
            return None
        lines = viewed(final["lines"], board, played)
        issue = grade(board, position, final["lines"])
        safe = [
            {"rank": item["rank"], **{key: item["line"].get(key) for key in FIELDS}}
            for item in lines
        ]
        return {"lines": safe, "work": final.get("work"), "comparison_issue": issue}
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return None


def scout_view(result):
    scout = result.get("scout")
    if not isinstance(scout, dict):
        return None
    return {"work": scout.get("work"), "role": "nomination only"}
