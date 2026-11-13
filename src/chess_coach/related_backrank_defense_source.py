"""Resolve one missed anchored back-rank threat from current owned evidence."""

from .back_rank_evidence import load
from .back_rank_practice_source import VERSION, resolve
from .decision_history import decision_board
from .mate_inspection_source import position_row
from .related_backrank_defense_shape import shape
from .related_capture_position import _features
from .related_capture_source import _opening


class UnsupportedDefense(ValueError):
    """The source is current but outside this anchored-defense slice."""


def _same_threat(anchor, played, mates, board):
    alternative, mate = anchor["alternative"]["uci"], anchor["mate"]["move"]["uci"]
    if alternative == played or mate not in mates:
        return False
    return shape(board, played, mate) == shape(board, alternative, mate)


def _witness(defense, board):
    if (defense.get("status"), defense.get("outcome"), defense.get("origin")) != (
        "opportunity",
        "allows",
        "anchored_preexisting",
    ):
        raise UnsupportedDefense("No anchored missed back-rank threat is available.")
    played = next(
        (entry for entry in defense["alternatives"] if entry["move"]["uci"] == defense["played"]),
        None,
    )
    if played is None:
        raise UnsupportedDefense("No anchored missed back-rank threat is available.")
    mates = {entry["move"]["uci"] for entry in played["back_rank"]}
    # A separate quiet witness must permit the same recorded mating move.
    for anchor in defense["anchors"]:
        if _same_threat(anchor, defense["played"], mates, board):
            return anchor
    raise UnsupportedDefense("The recorded mate has no matching anchored witness.")


def source_for_evidence(db, subject, evidence_id):
    evidence, fact, _ = load(db, evidence_id, subject)
    if evidence["operation"] != "prevent" or evidence["outcome"] != "failure":
        raise UnsupportedDefense("This source does not record a missed back-rank defense.")
    if evidence["review_status"] not in {"accepted", "unreviewed"}:
        raise ValueError("back-rank source unavailable")
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
    source["opening"] = _opening(db, evidence["position_id"])
    source["outcome"] = evidence["outcome"]
    return source
