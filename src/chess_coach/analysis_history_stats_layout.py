"""Recognize SQLite's internal planner-statistics tables before budgeting them."""

EXPECTED = {
    "sqlite_stat1": ("tbl", "idx", "stat"),
    "sqlite_stat4": ("tbl", "idx", "neq", "nlt", "ndlt", "sample"),
}


def names(connection):
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name IN ('sqlite_stat1','sqlite_stat4')"
        )
    ]


def supported(connection):
    observed = connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name GLOB 'sqlite_stat*'"
    )
    if any(row[0] not in EXPECTED for row in observed):
        return False
    for table, names in EXPECTED.items():
        present = connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if present and not _standard(connection, table, names):
            return False
    return True


def _standard(connection, table, names):
    sql = connection.execute(
        "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not _ddl(sql, table, names):
        return False
    rows = connection.execute(
        'SELECT name,type,"notnull",pk,hidden FROM pragma_table_xinfo(?)', (table,)
    ).fetchall()
    if [tuple(row) for row in rows] != [(name, "", 0, 0, 0) for name in names]:
        return False
    info = connection.execute(
        "SELECT wr,strict FROM pragma_table_list WHERE schema='main' AND name=?", (table,)
    ).fetchone()
    if info is None or tuple(info) != (0, 0):
        return False
    return not connection.execute("SELECT 1 FROM pragma_index_list(?) LIMIT 1", (table,)).fetchone()


def _ddl(sql, table, names):
    # Custom statistics schemas are outside the journal-page estimate.
    expected = "createtable" + table + "(" + ",".join(names) + ")"
    return sql is not None and "".join((sql[0] or "").lower().split()) == expected
