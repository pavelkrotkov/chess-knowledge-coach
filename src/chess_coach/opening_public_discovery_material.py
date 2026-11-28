"""Prepare material discoveries on both selected public branches."""

from .opening_public_discovery_material_coverage import COUNTS, collect
from .opening_public_mate_coverage import coverage, finish, unavailable
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def branch(db, binding, move, deadline):
    if binding["control"] == "unknown":
        return unavailable("nominal_context_unknown")
    found = _selected(db, binding, move, deadline)
    if found is None:
        return unavailable("deadline")
    rows, context = found
    selected = rows[:MAX_GAMES]
    kind = (
        "discovery_opportunity"
        if "discovery_opportunity" in binding["policy"]
        else "discovery_material"
    )
    result = coverage(context, selected, len(rows) > MAX_GAMES, binding, kind=kind)
    result.update(dict.fromkeys((*COUNTS, "unfinished_games"), 0))
    result["counts_scope"] = "completed_game_inspections"
    if kind == "discovery_opportunity":
        result.update(
            unfinished_roots=0,
            examples=[],
            counts_scope="returned_game_inspections_including_partial",
        )
    collect(db, selected, binding, move, deadline, result)
    return finish(result)
