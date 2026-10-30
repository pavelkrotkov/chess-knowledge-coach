"""Bind supported owned objective versions to the session snapshot."""

from .objective_capture_contract import (
    GAIN_OBJECTIVE,
    GAIN_VERSION,
    TARGET_OBJECTIVE,
    TARGET_VERSION,
)
from .objective_contract import OBJECTIVE, VERSION
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_fork_contract import GOAL as FORK_GOAL
from .objective_fork_contract import OBJECTIVE as FORK_OBJECTIVE
from .objective_fork_contract import VERSION as FORK_VERSION
from .objective_fork_defense_contract import GOAL as FORK_DEFENSE_GOAL
from .objective_fork_defense_contract import OBJECTIVE as FORK_DEFENSE_OBJECTIVE
from .objective_fork_defense_contract import VERSION as FORK_DEFENSE_VERSION
from .objective_pawn_contract import OBJECTIVE as PAWN_OBJECTIVE
from .objective_pawn_contract import VERSION as PAWN_VERSION
from .objective_pin_contract import GOAL as PIN_GOAL
from .objective_pin_contract import OBJECTIVE as PIN_OBJECTIVE
from .objective_pin_contract import VERSION as PIN_VERSION
from .objective_promotion_binding import public_binding, public_scope
from .objective_protection_contract import OBJECTIVE as PROTECTION_OBJECTIVE
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE
from .objective_short_source import VERSION as SHORT_VERSION


def matches(session, data, request):
    return (public_scope(session, request) and public_binding(data, request)) or (
        _scope(session, request) and _binding(session, data, request)
    )


def _scope(session, request):
    return (
        session["source_type"] == "own-game"
        and (session["source_version"], session["objective"])
        in {
            (FORK_VERSION, FORK_GOAL),
            (FORK_DEFENSE_VERSION, FORK_DEFENSE_GOAL),
            (PIN_VERSION, PIN_GOAL),
            (PAWN_VERSION, "preserve_pawn_win"),
            (PAWN_VERSION, "preserve_pawn_draw"),
            (PROTECTION_VERSION, "protect_threatened_piece"),
            (TARGET_VERSION, "capture_named_target"),
            (GAIN_VERSION, "bounded_material_gain"),
            (VERSION, "mate_in_one"),
            (SHORT_VERSION, "mate_within_two"),
            (DEFENSE_VERSION, "avoid_immediate_mate"),
        }
        and session["status"] == "needs_verification"
        and session["snapshot_hash"] == request["snapshot_hash"]
        and session["learner_color"] == request["learner_color"]
    )


def _binding(session, data, request):
    return (
        data.get("objective_version") == request["objective_version"]
        and (session["source_version"], data.get("objective_version"))
        in {
            (FORK_VERSION, FORK_OBJECTIVE),
            (FORK_DEFENSE_VERSION, FORK_DEFENSE_OBJECTIVE),
            (PIN_VERSION, PIN_OBJECTIVE),
            (PAWN_VERSION, PAWN_OBJECTIVE),
            (PROTECTION_VERSION, PROTECTION_OBJECTIVE),
            (TARGET_VERSION, TARGET_OBJECTIVE),
            (GAIN_VERSION, GAIN_OBJECTIVE),
            (VERSION, OBJECTIVE),
            (SHORT_VERSION, SHORT_OBJECTIVE),
            (DEFENSE_VERSION, DEFENSE_OBJECTIVE),
        }
        and data.get("history_mode") == request["history_mode"]
        and data.get("source_fingerprint") == request["source_hash"]
    )
