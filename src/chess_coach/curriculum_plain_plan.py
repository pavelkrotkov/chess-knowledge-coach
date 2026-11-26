"""Build an untimed plan while retaining the signed capture-policy scope."""

from .curriculum_capture_guard import plain
from .curriculum_cursor import resume_state
from .curriculum_page import build_page
from .curriculum_priority_cursor import upgrade


def build(db, prior, learner, corpus, limit, scan_limit, now, budget, project_root, new_state):
    if prior is None:
        state = upgrade(
            new_state(db, learner, corpus, limit, scan_limit, now),
            capture=project_root is not None and budget is not None,
        )
    else:
        state, now = resume_state(db, prior, learner, corpus, limit, scan_limit, now)
    page = build_page(db, state, learner, now, budget)
    return plain(db, page, state, learner, project_root, budget)
