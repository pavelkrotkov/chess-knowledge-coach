"""Revalidate legal attacking witnesses and safe immediate-mate defenses."""

from .back_rank_defense import observe
from .back_rank_practice_attack import attacks


def lines(board, fact, operation):
    if operation == "prevent":
        return _defenses(board, fact)
    if operation == "execute":
        return attacks(board, fact)
    raise ValueError("back-rank practice unavailable")


def _defenses(board, fact):
    expected = fact["defense"]
    actual = observe(board, board.parse_uci(fact["played"]))
    if actual != expected or actual["status"] != "opportunity":
        raise ValueError("back-rank defense unavailable")
    result = [
        item["move"]["uci"]
        for item in actual["alternatives"]
        if item["status"] == "complete" and not item["back_rank"] and not item["other_mates"]
    ]
    if not result:
        raise ValueError("back-rank defense unavailable")
    return result
