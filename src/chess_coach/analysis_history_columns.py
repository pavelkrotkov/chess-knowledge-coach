"""Supported rowid-table columns for analysis capacity planning."""

RUN_COLUMNS = {
    "id": ("INTEGER", 0, 1),
    "game_id": ("INTEGER", 1, 0),
    **{
        name: ("TEXT", 1, 0)
        for name in (
            "engine",
            "engine_version",
            "config_json",
            "binary_path",
            "binary_version",
            "nnue",
            "compatibility_json",
            "created_at",
        )
    },
}
PROFILE_COLUMNS = {
    "id": ("INTEGER", 0, 1),
    **{
        name: ("TEXT", 1, 0)
        for name in ("fingerprint", "config_json", "nnue", "compatibility_json")
    },
}
LINK_COLUMNS = {"run_id": ("INTEGER", 0, 1), "provenance_id": ("INTEGER", 1, 0)}
SETTING_COLUMNS = {"id": ("INTEGER", 0, 1), "compact": ("INTEGER", 1, 0)}


def columns(connection, table, expected):
    rows = connection.execute(
        'SELECT name,type,"notnull",pk,hidden FROM pragma_table_xinfo(?)', (table,)
    )
    found = {row[0]: (row[1].upper(), row[2], row[3]) for row in rows if row[4] == 0}
    count = connection.execute("SELECT count(*) FROM pragma_table_xinfo(?)", (table,)).fetchone()[0]
    table_info = connection.execute(
        "SELECT wr,strict FROM pragma_table_list WHERE schema='main' AND name=?", (table,)
    ).fetchone()
    return found == expected and count == len(expected) and tuple(table_info or ()) == (0, 0)
