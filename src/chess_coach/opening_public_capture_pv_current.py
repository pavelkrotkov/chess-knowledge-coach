"""Bind and recheck public PV capture preparations without running an engine."""

import sqlite3
from contextlib import closing

from .engine_report_cache import report_digests
from .fact_fingerprint import canonical, digest
from .opening_profile_lookup import guard
from .opening_public_comparison_engine import configuration
from .opening_public_proof_history import positions
from .opening_public_proof_source import MAX_GAMES, check
from .opening_recent_select import rows as select_rows


def _record(connection, binding, move, row, record, deadline):
    rows, candidates, _, safe = positions(
        connection, row[0], row[1], binding, move, deadline, all_moves=True
    )
    if not safe:
        raise ValueError("public capture history changed")
    by_ply = {item[0]: item for item in candidates}
    ply, board, recorded = by_ply[record["ply"]]
    if (
        recorded.uci() != record["recorded_uci"]
        or digest(canonical(rows[: ply - 1])) != record["history_sha256"]
    ):
        raise ValueError("public capture history changed")
    check(deadline)
    _, current = configuration(record["configuration"]["engine_path"], board)
    check(deadline)
    if current != record["configuration"]:
        raise ValueError("public capture configuration changed")


def verify(index, binding, branches, deadline):
    with (
        report_digests(),
        closing(
            sqlite3.connect(index[0].as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
        ) as connection,
    ):
        guard(connection, deadline)
        for label in ("played", "alternative"):
            records = branches[label]["records"]
            if not records:
                continue
            move = binding["source"][label]
            rows, _ = select_rows(
                connection,
                binding["source"]["parent"],
                move,
                binding["ply"],
                binding["control"],
            )
            by_game = {item[0]: item for item in rows[:MAX_GAMES]}
            for record in records:
                _record(connection, binding, move, by_game[record["record"]], record, deadline)
