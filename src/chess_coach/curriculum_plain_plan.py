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

        check_common(db, state, learner, project_root, budget)
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
