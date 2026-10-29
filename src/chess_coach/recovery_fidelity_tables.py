"""List supported tables and selectable columns with explicit bounds."""

MAX_OBJECTS = 4096
MAX_COLUMNS = 512


def tables(connection):
    result = []
    for namespace, name, kind, _, without_rowid, _ in connection.execute("PRAGMA main.table_list"):
        if namespace != b"main" or name == b"sqlite_schema":
            continue
        if kind == b"view":
            continue
        if kind != b"table":
            raise ValueError("unsupported database schema")
        if len(result) >= MAX_OBJECTS:
            raise ValueError("database schema exceeds supported limit")
        result.append((name, bool(without_rowid)))
    return result


def columns(connection, name):
    result = list(
        connection.execute("SELECT name,pk,hidden FROM pragma_table_xinfo(?)", (name.decode(),))
    )
    if not result or len(result) > MAX_COLUMNS or any(row[2] == 1 for row in result):
        raise ValueError("unsupported database schema")
    return result
