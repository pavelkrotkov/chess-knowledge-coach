"""Bind a purpose source to its independently collected report context."""

from .purpose_current import owned


def matches_context(snapshot, context):
    return (
        snapshot["board"].fen() == context["pre_move_fen"]
        and snapshot["position"]["uci"] == context["played_move"]
    )


def slot_matches_request(db, learner, slot):
    try:
        row = owned(db, slot["request_id"], learner)
    except ValueError:
        return False
    return row["game_id"] == slot["game_id"] and row["position_id"] == slot["position_id"]
