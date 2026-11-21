"""Complete owned-fork learning through the shared atomic transaction."""

from . import unified_fork_learning
from .unified_capture_completion import complete as complete_owned


def complete(db, attempt_id, subject, *, event_id=None):
    return complete_owned(db, attempt_id, subject, event_id=event_id, policy=unified_fork_learning)
