"""Select the history reconstruction required by an objective source."""

from .objective_contract import OWNED_HISTORY, STANDALONE
from .objective_history import before_answer
from .objective_pawn_contract import OBJECTIVE as PAWN_OBJECTIVE
from .objective_pawn_history import before_answer as pawn_before_answer
from .objective_promotion_contract import VERSION as PROMOTION_VERSION
from .objective_promotion_history import before_answer as promotion_before_answer


def supported(request):
    return request["history_mode"] == OWNED_HISTORY or (
        request["objective_version"] == PROMOTION_VERSION and request["history_mode"] == STANDALONE
    )


def replay(db, session, events, request):
    if request["objective_version"] == PROMOTION_VERSION:
        return promotion_before_answer(db, session, events)
    if request["objective_version"] == PAWN_OBJECTIVE:
        return pawn_before_answer(db, session, events)
    return before_answer(db, session, events)
