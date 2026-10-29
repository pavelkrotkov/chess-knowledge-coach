"""Resolve the target and reject ambiguous pre-move threats."""


def before_reason(before):
    if before is None:
        return "invalid_hypothetical_probe"
    if before["ambiguous"]:
        return "illegal_or_unresolved_attack"
    return "multiple_material_threats" if len(before["targets"]) > 1 else None


def target(before, following, move):
    if before["targets"]:
        old = next(iter(before["targets"]))
        return move.to_square if move.from_square == old else old
    return move.to_square if move.to_square in following["targets"] else None
