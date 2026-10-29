"""Find the exact WITHOUT ROWID primary order without temporary sorting."""

from .recovery_fidelity_schema import identifier


def _primary_index(connection, name):
    indexes = connection.execute("SELECT name,origin FROM pragma_index_list(?)", (name.decode(),))
    selected = [row[0] for row in indexes if row[1] == b"pk"]
    if len(selected) != 1:
        raise ValueError("unsupported database schema")
    return selected[0]


def _term(field):
    name, descending, collation, key = field
    if not name or not collation or not key:
        raise ValueError("unsupported database schema")
    direction = " DESC" if descending else " ASC"
    return identifier(name) + " COLLATE " + identifier(collation) + direction


def primary_order(connection, name):
    index = _primary_index(connection, name)
    fields = connection.execute(
        "SELECT name,desc,coll,key FROM pragma_index_xinfo(?)", (index.decode(),)
    )
    order = [_term(field) for field in fields if field[3]]
    if not order:
        raise ValueError("unsupported database schema")
    return ",".join(order)
