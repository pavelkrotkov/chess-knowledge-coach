"""Select the history reconstruction required by an objective source."""

from .objective_capture_contract import TARGET_OBJECTIVE
from .objective_contract import OWNED_HISTORY, STANDALONE
from .objective_created_contract import OBJECTIVE as CREATED_OBJECTIVE
from .objective_fork_contract import OBJECTIVE as FORK_OBJECTIVE
from .objective_history import before_answer
from .objective_pawn_contract import OBJECTIVE as PAWN_OBJECTIVE
from .objective_pawn_history import before_answer as pawn_before_answer
from .objective_promotion_contract import VERSION as PROMOTION_VERSION
from .objective_promotion_history import before_answer as promotion_before_answer
from .objective_protection_contract import OBJECTIVE as PROTECTION_OBJECTIVE
from .related_capture_assessment import HISTORY as CAPTURE_HISTORY


def supported(request):
    return (
        (
            request["objective_version"]
            in {TARGET_OBJECTIVE, FORK_OBJECTIVE, PROTECTION_OBJECTIVE, CREATED_OBJECTIVE}
            and request["history_mode"] == CAPTURE_HISTORY
        )
        or request["history_mode"] == OWNED_HISTORY
        or (
            request["objective_version"] == PROMOTION_VERSION
            and request["history_mode"] == STANDALONE
        )
    )


def replay(db, session, events, request):
    if (
        request["objective_version"]
        in {TARGET_OBJECTIVE, FORK_OBJECTIVE, PROTECTION_OBJECTIVE, CREATED_OBJECTIVE}
        and request["history_mode"] == CAPTURE_HISTORY
    ):
        from .related_capture_objective import before_answer as capture_before_answer

        return capture_before_answer(db, session, events)
    if request["objective_version"] == PROMOTION_VERSION:
        return promotion_before_answer(db, session, events)
    if request["objective_version"] == PAWN_OBJECTIVE:
        return pawn_before_answer(db, session, events)
    return before_answer(db, session, events)
