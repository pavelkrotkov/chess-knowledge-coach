"""Prove a supplied defense against an independently witnessed threat."""

import chess

from .back_rank_defense import observe
from .related_backrank_defense_shape import shape


def _same_bad_move(board, move, source):
    context = source["created_contrast"]
    geometry = (
        abs(chess.square_file(move.to_square) - chess.square_file(move.from_square)),
        abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square)),
    )
    return (
        board.piece_type_at(move.from_square) == context["mover"]
        and geometry == context["geometry"]
    )


def _safe_choice(result, move):
    # The supplied move must avoid every resolved immediate mate in the scan.
    good = next(
        (item for item in result["alternatives"] if item["move"]["uci"] == move.uci()), None
    )
    return bool(
        good and good["status"] == "complete" and not good["back_rank"] and not good["other_mates"]
    )


def _new_mates(item, before):
    return item["status"] == "complete" and not any(
        mate["move"]["uci"] in before for mate in item["back_rank"]
    )


def _matching_witness(board, item, source):
    bad = board.parse_uci(item["move"]["uci"])
    if not _same_bad_move(board, bad, source):
        return None
    for mate in item["back_rank"]:
        uci = mate["move"]["uci"]
        if shape(board, bad.uci(), uci) == source["threat_shape"]:
            return {"alternative": bad.uci(), "mate": uci}
    return None


def _created(board, move, source):
    result = observe(board, move, include_candidates=True)
    before = result.get("pre_move_candidates")
    if before is None or result.get("reason") == "incomplete_alternatives":
        return None
    if not _safe_choice(result, move):
        return None
    # All back-rank mates after the bad move must be absent from the pre-move probe.
    for item in result["alternatives"]:
        if not _new_mates(item, before):
            continue
        witness = _matching_witness(board, item, source)
        if witness:
            return witness
    return None


def proof(board, move, source):
    if source.get("threat_origin") == "newly_allowed":
        return _created(board, move, source)
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
