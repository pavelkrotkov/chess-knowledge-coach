"""Resolve a missed anchored or newly allowed back-rank mate from owned evidence."""

from .back_rank_evidence import load
from .back_rank_practice_source import VERSION, resolve
from .decision_history import decision_board
from .mate_inspection_source import position_row
from .related_backrank_defense_shape import shape
from .related_capture_position import _features
from .related_capture_source import _opening


class UnsupportedDefense(ValueError):
    """The current source is outside the supported defense-transfer scopes."""


def _same_threat(anchor, played, mates, board):
    alternative, mate = anchor["alternative"]["uci"], anchor["mate"]["move"]["uci"]
    if alternative == played or mate not in mates:
        return False
    return shape(board, played, mate) == shape(board, alternative, mate)


def _played(defense):
    if (defense.get("status"), defense.get("outcome")) != ("opportunity", "allows"):
        raise UnsupportedDefense("No missed back-rank threat is available.")
    played = next(
        (entry for entry in defense["alternatives"] if entry["move"]["uci"] == defense["played"]),
        None,
    )
    if played is None or not played["back_rank"]:
        raise UnsupportedDefense("No missed back-rank threat is available.")
    return played


def _witness(defense, board):
    played = _played(defense)
    if defense.get("origin") == "newly_allowed":
        return {"alternative": played["move"], "mate": played["back_rank"][0]}
    if defense.get("origin") != "anchored_preexisting":
        raise UnsupportedDefense("The back-rank threat origin is unavailable.")
    mates = {entry["move"]["uci"] for entry in played["back_rank"]}
    # A separate quiet witness must permit the same recorded mating move.
    for anchor in defense["anchors"]:
        if _same_threat(anchor, defense["played"], mates, board):
            return anchor
    raise UnsupportedDefense("The recorded mate has no matching anchored witness.")


def _created_contrast(board, anchor):
    bad = board.parse_uci(anchor["alternative"]["uci"])
    features = _features(
        board, bad, board.piece_at(bad.from_square), board.piece_at(board.king(board.turn))
    )
    return {
        "move": anchor["alternative"]["uci"],
        "san": anchor["alternative"]["san"],
        "mate": anchor["mate"]["move"]["uci"],
        "mate_san": anchor["mate"]["move"]["san"],
        "mover": features["mover"],
        "geometry": features["geometry"],
    }


def source_for_evidence(db, subject, evidence_id):
    evidence, fact, _ = load(db, evidence_id, subject)
    if evidence["operation"] != "prevent" or evidence["outcome"] != "failure":
        raise UnsupportedDefense("This source does not record a missed back-rank defense.")
    if evidence["review_status"] not in {"accepted", "unreviewed"}:
        raise ValueError("back-rank source unavailable")
    # Recheck the complete stored proof against original history before binding it.
    source = resolve(db, VERSION, str(evidence_id), subject)
    board = decision_board(db, position_row(db, evidence["position_id"]))
    defense = fact["payload"]["defense"]
    anchor = _witness(defense, board)
    safe = board.parse_uci(source["lines"][0])
    source["features"] = _features(
        board, safe, board.piece_at(safe.from_square), board.piece_at(board.king(board.turn))
    )
    source["threat_shape"] = shape(
        board, anchor["alternative"]["uci"], anchor["mate"]["move"]["uci"]
    )
    if defense["origin"] == "newly_allowed":
        source["threat_origin"] = "newly_allowed"
        source["created_contrast"] = _created_contrast(board, anchor)
    source["opening"] = _opening(db, evidence["position_id"])
    source["outcome"] = evidence["outcome"]
    return source
