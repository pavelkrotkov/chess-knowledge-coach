"""Build an untimed plan while retaining the signed capture-policy scope."""

from copy import deepcopy

from .curriculum_capture_guard import plain
from .curriculum_cursor import resume_state
from .curriculum_page import build_page
from .curriculum_priority_cursor import upgrade


def build(db, prior, learner, corpus, limit, scan_limit, now, budget, project_root, new_state):
    if prior is None:
        from .curriculum_priority_cursor import COMMON_POLICY, available

        capture = available(db, learner, budget)
        state = upgrade(
            new_state(db, learner, corpus, limit, scan_limit, now),
            capture=capture,
            policy=COMMON_POLICY if capture and limit == 1 else None,
        )
        from .curriculum_common_guard import check as check_common

        try:
            check_common(db, state, learner, project_root, budget)
        except ValueError as error:
            _fallback(state, budget, error)
    else:
        state, now = resume_state(db, prior, learner, corpus, limit, scan_limit, now)
    from .curriculum_capture_file_guard import initialize
    from .curriculum_cursor_codec import encode_cursor
    from .curriculum_priority_cursor import CAPTURE_FILE_POLICIES

    initialize(db, state, learner, budget)
    selection = None
    if state.get("priority_policy") in CAPTURE_FILE_POLICIES:
        selected = deepcopy(state)
        selected["capture_selection"] = True
        selection = encode_cursor(db, selected)
    page = build_page(db, state, learner, now, budget)
    page["plan_selection_cursor"] = selection
    return plain(db, page, state, learner, project_root, budget)


def _fallback(state, budget, error):
    from .curriculum_priority_cursor import CONTEXT_CAPTURE_POLICY

    if state["common_input"] is not None or str(error) not in {
        "practice source unavailable",
        "capture objective unavailable",
        "capture history unavailable",
        "capture source unavailable",
        "capture target unavailable",
        "fork source unavailable",
        "fork objective unavailable",
    }:
        raise error
    budget.check()
    state["priority_policy"] = CONTEXT_CAPTURE_POLICY
    state.pop("common_input")
    state.pop("common")
    return
