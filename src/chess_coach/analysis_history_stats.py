"""Analysis-specific allocation and bounded profile sampling."""

import hashlib
import sqlite3

from .analysis_provenance import source_table
from .fact_fingerprint import canonical

SAMPLE_LIMIT = 1024


def allocation(connection):
    tables = (
        "analysis_runs",
        "analysis_provenance",
        "analysis_run_provenance",
        "analysis_provenance_settings",
    )
    available = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name IN (?,?,?,?)", tables
        )
    }
    if "analysis_runs" not in available:
        raise ValueError("analysis table allocation unavailable")
    names = {"sqlite_schema"} | available
    for table in available:
        names.update(
            row[0] for row in connection.execute("SELECT name FROM pragma_index_list(?)", (table,))
        )
    result = {}
    for name in names:
        try:
            row = connection.execute(
                """SELECT sum(pgsize),sum(payload),sum(unused),
                sum(CASE WHEN pagetype='leaf' THEN ncell ELSE 0 END)
                FROM dbstat WHERE name=?""",
                (name,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError("analysis table allocation unavailable") from exc
        if row[0] is None:
            raise ValueError("analysis table allocation unavailable")
        result[name] = tuple(row)
    return result, available == set(tables)


def profiles(connection, deadline):
    fingerprints = set()
    rows = 0
    table = source_table(connection)
    for row in connection.execute(
        f"SELECT config_json,nnue,compatibility_json FROM {table} ORDER BY id LIMIT ?",
        (SAMPLE_LIMIT + 1,),
    ):
        deadline.check()
        rows += 1
        if rows > SAMPLE_LIMIT:
            break
        value = canonical(list(row)).encode("utf-8")
        fingerprints.add(hashlib.sha256(value).digest())
    return {
        "sampled_rows": min(rows, SAMPLE_LIMIT),
        "distinct_sampled_profiles": len(fingerprints),
        "repeated_sampled_rows": min(rows, SAMPLE_LIMIT) - len(fingerprints),
        "sample_complete": rows <= SAMPLE_LIMIT,
    }
