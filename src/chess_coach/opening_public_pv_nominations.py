"""Nominate bounded public source work and record unresolved coverage."""

from .opening_public_capture_pv_position import candidate


def nomination(board, recorded, deadline, result, defense):
    if defense:
        from .opening_public_defense_pv_position import nominate as defense_nominate

        result["witness_checked"] += 1
        nomination = defense_nominate(board, recorded, deadline)
        if nomination is None:
            return None
        if "outcome" in nomination:
            result["unsupported_positions"] += 1
            result["reasons"].append(nomination["reason"])
            return None
        kind = nomination["kind"]
    else:
        kind = "capture" if board.is_capture(recorded) else "quiet"
        if kind in result["attempted_kinds"]:
            return None
        result["witness_checked"] += 1
        if not candidate(board, recorded, deadline):
            return None
    return None if kind in result["attempted_kinds"] else kind
