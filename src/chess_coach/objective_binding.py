"""Bind supported owned objective versions to the session snapshot."""

from .discovery_defense_contract import PRACTICE as DISCOVERY_DEFENSE_VERSION
from .objective_binding_forks import BINDINGS as FORK_BINDINGS
from .objective_binding_scope import owned_scope, owned_snapshot_scope
from .objective_capture_contract import (
    GAIN_OBJECTIVE,
    GAIN_VERSION,
    TARGET_OBJECTIVE,
    TARGET_VERSION,
)
from .objective_contract import OBJECTIVE, VERSION
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_pawn_contract import OBJECTIVE as PAWN_OBJECTIVE
from .objective_pawn_contract import VERSION as PAWN_VERSION
from .objective_pin_contract import OBJECTIVE as PIN_OBJECTIVE
from .objective_pin_contract import VERSION as PIN_VERSION
from .objective_pin_prevent_contract import OBJECTIVE as PIN_PREVENT_OBJECTIVE
from .objective_pin_prevent_contract import VERSION as PIN_PREVENT_VERSION
from .objective_promotion_binding import public_binding, public_scope
from .objective_protection_contract import OBJECTIVE as PROTECTION_OBJECTIVE
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE
from .objective_short_source import VERSION as SHORT_VERSION
from .related_capture_objective import matches as capture_assessment
from .related_fork_assessment_scope import matches as fork_assessment


def matches(session, data, request):
    return (
        capture_assessment(session, data, request)
        or fork_assessment(session, data, request)
        or (public_scope(session, request) and public_binding(data, request))
        or (owned_scope(session, request) and _binding(session, data, request))
    )


def matches_short_terminal(session, data, request):
    return (
        session["status"] in {"needs_verification", "objective_verified"}
        and (session["source_version"], session["objective"]) == (SHORT_VERSION, "mate_within_two")
        and owned_snapshot_scope(session, request)
        and _binding(session, data, request)
    )


def _binding(session, data, request):
    return (
        data.get("objective_version") == request["objective_version"]
        and (session["source_version"], data.get("objective_version"))
        in {
            *FORK_BINDINGS,
            (PIN_VERSION, PIN_OBJECTIVE),
            (PIN_PREVENT_VERSION, PIN_PREVENT_OBJECTIVE),
            (PAWN_VERSION, PAWN_OBJECTIVE),
            (PROTECTION_VERSION, PROTECTION_OBJECTIVE),
            (TARGET_VERSION, TARGET_OBJECTIVE),
            (GAIN_VERSION, GAIN_OBJECTIVE),
            (VERSION, OBJECTIVE),
            (SHORT_VERSION, SHORT_OBJECTIVE),
            (DEFENSE_VERSION, DEFENSE_OBJECTIVE),
            (DISCOVERY_DEFENSE_VERSION, DEFENSE_OBJECTIVE),
        }
        and data.get("history_mode") == request["history_mode"]
        and data.get("source_fingerprint") == request["source_hash"]
    )
