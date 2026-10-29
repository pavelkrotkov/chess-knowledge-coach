"""Reject analysis-only handoffs that would lose selection provenance."""


def require_merge_safe(source):
    table = source.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='deep_selection_runs'"
    ).fetchone()
    if table and source.connection.execute("SELECT 1 FROM deep_selection_runs LIMIT 1").fetchone():
        raise ValueError("analysis handoff does not support selection history")
