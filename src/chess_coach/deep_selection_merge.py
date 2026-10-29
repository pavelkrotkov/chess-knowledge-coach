"""Reject analysis-only handoffs that would lose owned deep provenance."""


def require_merge_safe(source):
    _reject_material_history(source)
    for table in (
        "deep_selection_runs",
        "deep_analysis_jobs",
        "deep_analysis_attempts",
        "deep_analysis_alternatives",
        "deep_analysis_current",
    ):
        exists = source.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists and source.connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise ValueError("analysis handoff does not support selection or deep history")


def _reject_material_history(source):
    exists = source.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?", ("table", "detector_runs")
    ).fetchone()
    if (
        exists
        and source.connection.execute(
            "SELECT 1 FROM detector_runs WHERE producer=? LIMIT 1", ("material-opportunity",)
        ).fetchone()
    ):
        raise ValueError("analysis handoff does not support material history")
