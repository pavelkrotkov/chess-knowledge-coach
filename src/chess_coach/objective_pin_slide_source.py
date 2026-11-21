"""Bind a stronger owned relative-slide witness to current pin evidence."""

from .objective_pin_prevent_contract import VERSION as PREVENT_VERSION
from .objective_pin_prevent_preflight import valid_key
from .objective_pin_prevent_source import resolve as resolve_prevention
from .objective_pin_slide_budget import LIMIT, PIN_REVALIDATION, scope, take
from .objective_pin_slide_contract import GOAL, OBJECTIVE, VERSION
from .objective_pin_slide_proof import prove
from .pin_defense_success import MAX_ROOT_MOVES
from .recurrence_snapshot import read_snapshot
from .related_pin_slide_owned import checked


def resolve(db, version, key, subject):
    if not valid_key(version, key, VERSION):
        raise ValueError("pin slide source unavailable")
    with scope(), read_snapshot(db):
        source = resolve_prevention(db, PREVENT_VERSION, key, subject)
        bound = source["provenance"]["pin_prevention"]
        if bound["origin"] != "existing" or bound["kind"] != "relative_pin":
            raise ValueError("pin slide source unavailable")
        take(PIN_REVALIDATION)
        board, _named, _bad = checked(db, source, bound)
        move = _exemplar(board, bound)
        source["objective"] = GOAL
        source["lines"] = [move.uci()]
        source["provenance"].update(objective_version=OBJECTIVE, slide_work_limit=LIMIT)
        return source


def _exemplar(board, bound):
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    take(len(moves) + 1)
    if len(moves) > MAX_ROOT_MOVES:
        raise ValueError("pin slide work limit")
    for move in moves:
        if prove(board, move, bound) is not None:
            return move
    raise ValueError("pin slide source unavailable")
