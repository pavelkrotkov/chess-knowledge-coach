"""Describe qualified subsets without treating missing evidence as zero."""

from .opening_fit_later_rank import rank


def fit(decision, row, owned, public, nominal):
    move = row["choice"]["uci"]
    if owned.get("status") != "checked" or move not in public:
        return {"status": "unknown"}
    moves = [decision["played_uci"], move]
    if moves[0] not in public:
        return {"status": "unknown"}
    winner = rank(moves, owned.get("branches", {}), public, nominal)
    if winner == move:
        return {
            "status": "supported",
            "basis": "conditional_center_opportunities",
            "selection": move,
        }
    if winner == decision["played_uci"] and row["admission"]["played_admitted"]:
        return {
            "status": "not_selected",
            "basis": "played_branch_preferred_in_pair",
            "selection": winner,
        }
    return {"status": "unknown", "basis": "no_qualified_separation"}


def selected(rows, field):
    eligible = list(
        dict.fromkeys(
            item["selection"] for row in rows if (item := row.get(field, {})).get("selection")
        )
    )
    return {
        "eligible": eligible,
        "winner": eligible[0] if len(eligible) == 1 else None,
        "tie": len(eligible) > 1,
        "provisional": any(row.get(field, {}).get("status") == "provisional" for row in rows),
    }
