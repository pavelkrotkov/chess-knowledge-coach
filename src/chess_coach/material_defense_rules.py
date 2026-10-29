"""Resolve the target and validate ordinary moves that remove its attacker."""


def before_reason(before):
    if before is None:
        return "invalid_hypothetical_probe"
    if len(before["targets"]) > 1:
        return "multiple_material_threats"
    if not before["targets"] and before["uncertain"]:
        return "illegal_or_unresolved_attack"
    if before["targets"] and next(iter(before["targets"])) in before["uncertain"]:
        return "illegal_or_unresolved_attack"
    return None


def target(before, following, move):
    if before["targets"]:
        old = next(iter(before["targets"]))
        return move.to_square if move.from_square == old else old
    return move.to_square if move.to_square in following["targets"] else None
