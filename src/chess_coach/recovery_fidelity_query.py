"""Construct indexed, deterministic SQLite row scans."""

from .recovery_fidelity_index import primary_order
from .recovery_fidelity_schema import identifier
from .recovery_fidelity_tables import columns


def _rowid(fields):
    names = {item[0].lower() for item in fields}
    for candidate in (b"rowid", b"_rowid_", b"oid"):
        if candidate not in names:
            return identifier(candidate)
    raise ValueError("unsupported database schema")


def query_for(connection, name, without_rowid):
    fields = columns(connection, name)
    names = [identifier(field[0]) for field in fields]
    rowid = None if without_rowid else _rowid(fields)
    selected = ([rowid] if rowid else []) + names + ["typeof(" + item + ")" for item in names]
    order = primary_order(connection, name) if without_rowid else rowid
    return "SELECT " + ",".join(selected) + " FROM " + identifier(name) + " ORDER BY " + order
