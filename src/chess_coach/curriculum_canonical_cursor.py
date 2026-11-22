"""Signed source and quota state for the canonical promotion pass."""

from .curriculum_cursor_capture import _digest
from .curriculum_cursor_values import integer
from .curriculum_public_cursor import STATUSES
from .fact_fingerprint import canonical, digest
from .plan_promotion_catalog import SHA, TASKS, VERSION

POLICY = "canonical-promotion-mix-v1-owned-one-then-second"
CONTEXTS = {"unchecked", "continuation", "first_recorded", "unavailable", "incomplete"}


def fields():
    return {
        "mix_policy": policy_binding(),
        "canonical_version": VERSION,
        "canonical_sha": SHA,
        "canonical_tasks": TASKS,
        "canonical_context": "unchecked",
        "canonical_scope": None,
        "canonical_after": 0,
        "canonical_examined": 0,
        "canonical_pending": None,
        "canonical_binding": None,
        "canonical_status": "unchecked",
        "capture_mix": "unchecked",
        "fork_mix": "unchecked",
    }


def validate(state):
    # Both the catalog bytes and policy remain pinned across continuation pages.
    if (
        state["mix_policy"],
        state["canonical_version"],
        state["canonical_sha"],
        state["canonical_tasks"],
    ) != (policy_binding(), VERSION, SHA, TASKS):
        raise ValueError("canonical mix policy changed")
    if state["canonical_context"] not in CONTEXTS or state["canonical_status"] not in STATUSES:
        raise ValueError("invalid canonical state")
    if any(state[key] not in STATUSES for key in ("capture_mix", "fork_mix")):
        raise ValueError("invalid owned mix state")
    if not integer(state["canonical_after"], 0, 4) or not integer(
        state["canonical_examined"], 0, 2**63 - 1
    ):
        raise ValueError("invalid canonical position")
    _bindings(state)


def _bindings(state):
    for key in ("canonical_scope", "canonical_binding", "canonical_pending"):
        if state[key] is not None and not _digest(state[key]):
            raise ValueError("invalid canonical binding")
    # A bound task owns the scheduled-conflict cursor until it is resolved.
    if state["canonical_pending"] is None:
        if state["phase"] == "canonical" and state["scheduled_after"]:
            raise ValueError("orphaned canonical conflict")
        return
    if state["phase"] != "canonical":
        raise ValueError("unexpected canonical candidate")


def policy_binding():
    from .objective_capture_contract import TARGET_OBJECTIVE, TARGET_VERSION
    from .objective_fork_contract import MISS_OBJECTIVE, MISS_VERIFIER, MISS_VERSION
    from .objective_promotion_contract import FORCE, NOW, VERIFIER
    from .objective_promotion_contract import VERSION as OBJECTIVE_VERSION
    from .public_mate_contract import BINDING as PUBLIC_BINDING
    from .unified_canonical_forced_learning import MAPPER as FORCED_MAPPER
    from .unified_canonical_forced_learning import POLICY as FORCED_POLICY
    from .unified_canonical_promotion_learning import MAPPER as IMMEDIATE_MAPPER
    from .unified_canonical_promotion_learning import POLICY as IMMEDIATE_POLICY
    from .unified_capture_learning import MAPPER as CAPTURE_MAPPER
    from .unified_capture_learning import POLICY as CAPTURE_POLICY
    from .unified_fork_learning import MAPPER as FORK_MAPPER
    from .unified_fork_learning import POLICY as FORK_POLICY
    from .unified_public_mate_learning import MAPPER as PUBLIC_MAPPER
    from .unified_public_mate_learning import POLICY as PUBLIC_POLICY

    data = [
        TARGET_OBJECTIVE,
        TARGET_VERSION,
        CAPTURE_POLICY,
        CAPTURE_MAPPER,
        MISS_OBJECTIVE,
        MISS_VERIFIER,
        MISS_VERSION,
        FORK_POLICY,
        FORK_MAPPER,
        PUBLIC_BINDING,
        PUBLIC_POLICY,
        PUBLIC_MAPPER,
        NOW,
        FORCE,
        OBJECTIVE_VERSION,
        VERIFIER,
        IMMEDIATE_POLICY,
        IMMEDIATE_MAPPER,
        FORCED_POLICY,
        FORCED_MAPPER,
    ]
    return POLICY + ":" + digest(canonical(data))
