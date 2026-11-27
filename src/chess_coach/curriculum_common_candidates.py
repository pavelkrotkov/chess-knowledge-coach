"""Resolve both owned candidates and their shared scheduled-prompt frontier."""

from .curriculum_capture_conflicts import scheduled
from .curriculum_capture_witnesses import pending
from .curriculum_common_cursor import bind, finish
from .fact_fingerprint import canonical, digest


def _binding(identity, options, fork):
    return digest(canonical([pending(identity, options), fork["binding"]]))


def _scan(db, state, scan, options, fork, check, binding):
    common = bind(state, binding)
    combined = [*options, (fork, None)]
    key = "capture_pending" if state["phase"] == "capture" else "fork_pending"
    state[key] = binding
    if common["complete"]:
        return (
            {
                candidate["prompt_key"]
                for i, (candidate, _) in enumerate(combined)
                if common["matches"] & (1 << i)
            },
            None,
            None,
        )
    matched, status, reason = scheduled(db, state, scan, combined, check, common=True)
    if status is not None:
        return None, status, reason
    finish(state)
    return matched, None, None


def collect(db, state, scan, check, bundle):
    options, identity = bundle["options"], bundle["identity"]
    advisory, fork, focus = bundle["advisory"], bundle["fork"], bundle["fork_focus"]
    if not options or fork is None:
        if state["common"] is not None:
            raise ValueError("common sources changed; restart the plan")
        return None
    state["priority"]["capture_sources"] = identity
    matched, status, reason = _scan(
        db, state, scan, options, fork, check, _binding(identity, options, fork)
    )
    return options, fork, focus, matched, status, reason, advisory
