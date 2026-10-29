"""Count unknown metadata with bounded indexed lookups."""

from .style_time_projection import VERSION


def uncertain_count(connection, subject, limit):
    counts = []
    for side in ("white", "black"):
        rows = connection.execute(
            f"""SELECT 1 FROM style_game_times WHERE status='unknown_time'
            AND version=? AND {side}_identity=? LIMIT ?""",
            (VERSION, subject, limit + 1),
        )
        counts.append(len(list(rows)))
    unresolved = connection.execute(
        "SELECT 1 FROM style_game_times WHERE status IN ('stale','unknown_identity') LIMIT ?",
        (limit + 1,),
    )
    stale = len(list(unresolved))
    for status in ("current", "unknown_time"):
        for operator in ("<", ">"):
            mismatched = connection.execute(
                f"SELECT 1 FROM style_game_times WHERE status=? AND version {operator} ? LIMIT ?",
                (status, VERSION, limit + 1),
            )
            stale += len(list(mismatched))
    return sum(counts), stale


def has_unknown(coverage):
    return any(
        coverage[key]
        for key in (
            "unknown_time_lower_bound",
            "unknown_ownership_global_lower_bound",
            "candidate_recheck_failed",
        )
    )
