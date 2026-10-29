"""Read a bounded logical SQLite schema and reject unsupported table kinds."""

MAX_OBJECTS = 4096


def identifier(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", "strict")
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("unsupported database schema")
    return '"' + value.replace('"', '""') + '"'


def schema(connection):
    result = {}
    size = 0
    cursor = connection.execute("SELECT type,name,tbl_name,sql FROM main.sqlite_schema")
    for row in cursor:
        if len(result) >= MAX_OBJECTS:
            raise ValueError("database schema exceeds supported limit")
        size += sum(len(value) for value in row if isinstance(value, bytes))
        if size > 16 * 1024 * 1024:
            raise ValueError("database schema exceeds supported limit")
        key = (row[0], row[1])
        if key in result:
            raise ValueError("unsupported database schema")
        result[key] = row[2:]
    return result
