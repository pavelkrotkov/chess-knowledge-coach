"""Recheck each source-bound transfer family when a session resumes."""


def require_current(db, row, snapshot_hash):
    from .related_fork_avoidance_current import require_current as require_avoidance
    from .related_fork_current import require_current as require_fork
    from .related_fork_prevention_current import require_current as require_prevention
    from .related_mate_current import require_current as require_mate
    from .related_pin_current import require_current as require_pin
    from .related_protection_current import require_current as require_protection

    require_fork(db, row, snapshot_hash)
    require_protection(db, row, snapshot_hash)
    require_prevention(db, row, snapshot_hash)
    require_avoidance(db, row, snapshot_hash)
    require_mate(db, row, snapshot_hash)
    require_pin(db, row, snapshot_hash)
