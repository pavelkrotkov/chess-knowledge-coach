"""Bind fork evidence to the active qualified mapper scope."""

from .fork_contract import MAPPER, SCOPE, VERSION


def matches(db, evidence):
    row = db.connection.execute(
        "SELECT producer,mapper_version,scope_key,subject,position_id,operation,status FROM mapping_runs WHERE id=?",
        (evidence["mapping_run_id"],),
    ).fetchone()
    return bool(
        row
        and tuple(row)
        == (
            MAPPER,
            VERSION,
            SCOPE,
            evidence["subject"],
            evidence["position_id"],
            "execute",
            "active",
        )
    )
