"""Store optional binary digests without changing their public representation."""


def settings(connection):
    if connection.execute("PRAGMA user_version").fetchone()[0] < 35:
        return _legacy(connection), False
    row = connection.execute("SELECT compact FROM digest_settings WHERE id=1").fetchone()
    if row is None:
        raise ValueError("digest settings unavailable")
    return bool(row[0]), True


def _legacy(connection):
    setting = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='digest_settings'"
    ).fetchone()
    if not setting:
        return False
    row = connection.execute("SELECT compact FROM digest_settings WHERE id=1").fetchone()
    if row is None or row[0]:
        raise ValueError("digest schema unavailable")
    return False


def pack(value, compact):
    return bytes.fromhex(value) if compact else value


def unique_id(rows):
    if len(rows) > 1:
        raise ValueError("duplicate digest identity")
    return rows[0][0] if rows else None


def lookup(connection, query, params, table, *, modern):
    rows = connection.execute(query, params).fetchall()
    run_id = unique_id(rows)
    if rows and not modern and any(isinstance(value, bytes) for value in rows[0][1:]):
        raise ValueError("digest schema unavailable")
    if run_id is None:
        return None
    return connection.execute(f"SELECT * FROM {table} WHERE id=?", (run_id,)).fetchone()
