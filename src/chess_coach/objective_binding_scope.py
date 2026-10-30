"""Check exact owned objective scope before any source work."""

from .objective_capture_contract import GAIN_VERSION, TARGET_VERSION
from .objective_contract import VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_fork_contract import GOAL as FORK_GOAL
from .objective_fork_contract import VERSION as FORK_VERSION
from .objective_fork_defense_contract import GOAL as FORK_DEFENSE_GOAL
from .objective_fork_defense_contract import VERSION as FORK_DEFENSE_VERSION
from .objective_pawn_contract import VERSION as PAWN_VERSION
from .objective_pin_contract import GOAL as PIN_GOAL
from .objective_pin_contract import VERSION as PIN_VERSION
from .objective_pin_prevent_contract import GOAL as PIN_PREVENT_GOAL
from .objective_pin_prevent_contract import VERSION as PIN_PREVENT_VERSION
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_short_source import VERSION as SHORT_VERSION


def owned_scope(session, request):
    return (
        session["source_type"] == "own-game"
        and (session["source_version"], session["objective"])
        in {
            (FORK_VERSION, FORK_GOAL),
            (FORK_DEFENSE_VERSION, FORK_DEFENSE_GOAL),
            (PIN_VERSION, PIN_GOAL),
            (PIN_PREVENT_VERSION, PIN_PREVENT_GOAL),
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
