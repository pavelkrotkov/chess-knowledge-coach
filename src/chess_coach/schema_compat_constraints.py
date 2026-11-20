"""Capture exact indexes, triggers and foreign keys for legacy validation."""


def constraints(connection, tables):
    definitions = {
        (row[0], row[1]): row[2]
        for row in connection.execute(
            "SELECT name,type,sql FROM sqlite_master "
            "WHERE type IN ('index','trigger') AND sql IS NOT NULL"
        )
    }
    foreign = {}
    indexes = {}
    for table in tables:
        foreign[table] = sorted(
            tuple(row)
            for row in connection.execute("SELECT * FROM pragma_foreign_key_list(?)", (table,))
        )
        rows = connection.execute(
            'SELECT name,"unique",origin,partial FROM pragma_index_list(?) ORDER BY name',
            (table,),
        ).fetchall()
        indexes[table] = [
            (
                tuple(row),
                [
                    tuple(part)
                    for part in connection.execute("SELECT * FROM pragma_index_xinfo(?)", (row[0],))
                ],
            )
            for row in rows
        ]
    return definitions, foreign, indexes


def columns(connection, name):
    return {
        (row[1], row[2].upper(), row[3], row[5])
        for row in connection.execute("SELECT * FROM pragma_table_info(?)", (name,))
    }


def columns_match(connection, expected):
    return all(columns(connection, table) == value for table, value in expected.items())
