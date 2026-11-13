"""Derive a rechecked relative-pin slide from an owned exposure witness."""

from .objective_pin_prevent_contract import VERSION
from .objective_pin_prevent_source import resolve
from .pin_defense_success import MAX_ROOT_MOVES
from .related_capture_source import _opening
from .related_pin_contract import UnsupportedPinTransfer
from .related_pin_prevent_shape import features
from .related_pin_slide_proof import slide
from .related_pin_slide_witness import checked


def _choose(board, named):
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(moves) > MAX_ROOT_MOVES:
        raise UnsupportedPinTransfer("relative pin slide work limit")
    good = next((move for move in moves if slide(board, move, *named)), None)
    if good is None:
        raise UnsupportedPinTransfer("relative pin slide unavailable")
    return good


def source_slide(db, subject, evidence_id):
    source = resolve(db, VERSION, str(evidence_id), subject)
    bound = source["provenance"]["pin_prevention"]
    if (bound["origin"], bound["kind"]) != ("existing", "relative_pin"):
        raise UnsupportedPinTransfer("relative pin slide unavailable")
    board, named, bad = checked(db, source, bound)
    good = _choose(board, named)
    attacker, pinned = named
    source["features"] = {**features(board, good, attacker, pinned), "origin": "slide"}
    source["slide"] = {"move": good.uci(), "bad": bad.uci()}
    source["opening"] = _opening(db, source["provenance"]["position_id"])
    source["outcome"] = source["provenance"]["source_outcome"]
    return source
