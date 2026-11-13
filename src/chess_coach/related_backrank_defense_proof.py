"""Prove a supplied defense against an independently witnessed threat."""

from .back_rank_defense import observe
from .related_backrank_defense_shape import shape


def proof(board, move, source):
    result = observe(board, move)
    if (result.get("status"), result.get("outcome"), result.get("origin")) != (
        "opportunity",
        "avoids",
        "anchored_preexisting",
    ):
        return None
    for anchor in result["anchors"]:
        bad, mate = anchor["alternative"]["uci"], anchor["mate"]["move"]["uci"]
        if shape(board, bad, mate) == source["threat_shape"]:
            return {"alternative": bad, "mate": mate}
    return None
