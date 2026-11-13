"""Recheck each source-bound transfer family when a session resumes."""


def require_current(db, row, snapshot_hash, *, fork_check=None, fork_cache=None):
    from .related_backrank_current import require_current as require_backrank
    from .related_backrank_defense_current import require_current as require_backrank_defense
    from .related_created_current import require_current as require_created
    from .related_discovery_current import require_current as require_discovery
    from .related_fork_avoidance_current import require_current as require_avoidance
    from .related_fork_current import require_current as require_fork
    from .related_fork_prevention_current import require_current as require_prevention
    from .related_mate_current import require_current as require_mate
    from .related_pin_current import require_current as require_pin
    from .related_protection_current import require_current as require_protection

    require_created(db, row, snapshot_hash)
    require_discovery(db, row, snapshot_hash)
    require_fork(db, row, snapshot_hash, check=fork_check, cache=fork_cache)
    require_protection(db, row, snapshot_hash)
    require_prevention(db, row, snapshot_hash)
    require_avoidance(db, row, snapshot_hash)
    require_mate(db, row, snapshot_hash)
    require_pin(db, row, snapshot_hash)
    require_backrank(db, row, snapshot_hash)
    require_backrank_defense(db, row, snapshot_hash)
