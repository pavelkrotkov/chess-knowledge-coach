"""Sign and recheck one exact capture-practice recommendation."""

from .curriculum_prerequisite_token import encode

POLICY = "capture-practice-offer-v1"
CONTEXT_POLICY = "capture-practice-offer-v2:context-v1"
COMMON_POLICY = "common-practice-offer-v1"
COMMON_WINDOW_POLICY = "common-window-offer-v1"


def issue(db, state, item, goal, expires, *, window=None):
    from .curriculum_priority_cursor import COMMON_POLICY as COMMON_CURSOR
    from .curriculum_priority_cursor import CONTEXT_CAPTURE_POLICY

    if state["priority_policy"] == COMMON_CURSOR:
        policy = COMMON_POLICY
        binding = {
            "revision": state["revision"],
            "common_input": state["common_input"],
            "corpus_version": state["corpus_version"],
            "as_of": state["as_of"],
        }
        if window is not None:
            from .opening_context_launch_scope import _scope

            policy = COMMON_WINDOW_POLICY
            binding["window_scope"] = _scope(window)
    else:
        policy = CONTEXT_POLICY if state["priority_policy"] == CONTEXT_CAPTURE_POLICY else POLICY
        binding = {
            "revision": state["revision"],
            "capture_input": state["priority"]["capture_input"],
            "capture_sources": state["priority"]["capture_sources"],
        }
    return encode(
        db,
        [
            policy,
            state["subject_hash"],
            goal,
            expires,
            item["source_type"],
            item["source_version"],
            item["source_key"],
            binding,
            "unified",
        ],
    )


def token_policy(db, token):
    from .curriculum_prerequisite_token import _decode

    return _decode(db, token)[0] if token is not None else None
