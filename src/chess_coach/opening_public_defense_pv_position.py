"""Nominate and evaluate a recorded public defense using actual bounded PVs."""

from .material_ambiguity import ambiguous
from .material_defense import defense_observation
from .material_defense_probe import candidate
from .opening_public_capture_pv_position import check
from .opening_public_capture_pv_session import analyze
from .opening_queue_reference import public


def nominate(board, recorded, deadline):
    def within():
        check(deadline)

    probe = candidate(board, recorded.uci(), check=within)
    if probe is None:
        return None
    if "outcome" in probe:
        return probe
    target = probe["target"]
    kind = "threat_remains" if target in probe["following"]["targets"] else "threat_removed"
    return {"kind": kind}


def observe(board, recorded, engine, deadline):
    def within():
        check(deadline)

    within()
    config, result = analyze(board, recorded.uci(), engine, deadline)
    within()
    qualified = public(result, recorded.uci(), board)
    observed = ambiguous("material_protection", "native_reference_unavailable")
    if qualified:
        best = result["lines"][0]
        actual = next(line for line in result["lines"] if line["root_move"] == recorded.uci())
        observed = defense_observation(board, recorded.uci(), best, actual, check=within)
        if observed is None:
            observed = ambiguous("material_protection", "defense_unavailable")
    within()
    return {
        "configuration": config,
        "native": result,
        "qualified": qualified,
        "observation": observed,
    }
