"""Confirm a final result uses the played root and scout nominee."""

from .purpose_lines import roots, valid_pair


def matches(result, played):
    scout = result.get("scout", {})
    final = result.get("final", {})
    scout_lines = scout.get("lines", [])
    if not valid_pair(scout_lines) or not valid_pair(final.get("lines", [])):
        return False
    nominee = next((move for move in roots(scout_lines) if move != played), None)
    if nominee is None:
        return False
    expected = {played, nominee}
    return set(final.get("roots", [])) == expected and set(roots(final["lines"])) == expected
