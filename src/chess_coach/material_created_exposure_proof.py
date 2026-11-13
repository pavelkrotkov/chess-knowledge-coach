"""Prove one recorded created exposure under the existing material bounds."""

from .material_defense_probe import candidate
from .pawn_scope import history_known


def proof(prepared, fact):
    board = prepared["board"]
    if not history_known(board) or fact["kind"] != "material_protection":
        return None
    probe = candidate(board, prepared["context"]["played_move"])
    if not probe or "outcome" in probe:
        return None
    if probe["before"]["targets"] or probe["before"]["uncertain"]:
        return None
    played = fact["played"]
    move, target = probe["move"], probe["target"]
    after = board.copy()
    after.push(move)
    reply = after.parse_uci(played["uci"][1])
    if any(
        (
            reply.to_square != target,
            not after.is_capture(reply),
            reply.uci() not in probe["following"]["targets"].get(target, []),
            played["material_delta"] > -3,
        )
    ):
        return None
    return {
        "move": board.san(move),
        "piece": fact["target_piece"],
        "target": fact["target"],
        "capture": after.san(reply),
        "alternative": fact["best"]["san"][0],
    }
