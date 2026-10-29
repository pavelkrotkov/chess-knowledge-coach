"""Match automatic mate and pawn facts to their versioned mappings."""


def mate_ok(row, fact):
    from .mate_selection import mapping_skill

    payload = fact["payload"]
    try:
        return (
            row["mapper_version"] == "1.1.0"
            and row["operation"] == "execute"
            and payload.get("status") == "opportunity"
            and mapping_skill(payload) == row["skill"]
        )
    except (KeyError, TypeError):
        return False


def pawn_ok(row, fact):
    from .pawn_coach_mapping import operation

    try:
        return (
            row["mapper_version"] == "1.0.0"
            and row["skill"] == "king_pawn_endgame"
            and operation(fact["payload"]) == row["operation"]
        )
    except (KeyError, TypeError):
        return False


def backrank_ok(row, fact):
    from .back_rank_outcomes import outcomes

    try:
        return (
            row["mapper_version"] == "1.0.0"
            and row["skill"] == "back_rank"
            and (row["operation"], row["outcome"]) in outcomes(fact["payload"])
        )
    except (KeyError, TypeError):
        return False
