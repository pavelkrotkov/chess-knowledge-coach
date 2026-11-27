"""Check ownership and revision before renewing a practice window."""

from .curriculum_cursor import resume_state, revision
from .curriculum_window_policy import check_policy, common_renewal
from .curriculum_window_renew import _renew
from .fact_fingerprint import digest
from .mastery_time import parse_utc


def checked_renew(db, value, learner, version, scan_limit, now, minutes, budget):
    state = value["state"]
    if state["subject_hash"] != digest(learner):
        raise ValueError("practice window owner changed")
    if state["corpus_version"] != version or state["scan_limit"] != scan_limit:
        raise ValueError("practice window scope changed")
    check_policy(state)
    from .curriculum_priority_cursor import CAPTURE_POLICIES

    policy = state.get("priority_policy")
    common_renewal(policy, minutes, budget)
    root = getattr(budget, "project_root", None)
    if policy in CAPTURE_POLICIES:
        from .curriculum_capture_file_guard import for_policy

        before_files = for_policy(db, learner, root, policy)
    else:
        before_files = None
    capture_changed = False
    if state["revision"] == revision(db):
        resume_state(
            db, state, learner, version, state["limit"], scan_limit, parse_utc(state["as_of"])
        )
        capture_changed = _changed(db, state, learner, root, budget)
    result = _renew(
        db,
        value,
        learner,
        version,
        scan_limit,
        now,
        minutes,
        budget,
        capture_changed=capture_changed,
    )
    if result["state"] is not state and hasattr(budget, "common_choice"):
        del budget.common_choice
    _carry_files(db, result, learner, root, before_files)
    return result


def _carry_files(db, result, learner, root, before):
    if before is None:
        return
    from .curriculum_capture_file_guard import for_policy
    from .curriculum_priority_cursor import CAPTURE_FILE_POLICIES

    policy = result["state"].get("priority_policy")
    if before != for_policy(db, learner, root, policy):
        raise ValueError("capture practice changed; restart the plan")
    if policy in CAPTURE_FILE_POLICIES:
        # Carry the pre-history observation through window initialization.
        result["state"]["capture_files"] = before


def _changed(db, state, learner, root, budget):
    from .curriculum_capture_guard import changed
    from .curriculum_priority_cursor import COMMON_POLICY

    try:
        return changed(db, state, learner, root, budget)
    except ValueError as error:
        if (
            state.get("priority_policy") != COMMON_POLICY
            or str(error) != "common practice changed; restart the plan"
        ):
            raise
        return True
