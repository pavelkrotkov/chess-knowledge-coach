"""Construct a stable, private in-memory source snapshot for hashing."""


def source_payload(game, color, positions, lines, config):
    clean_lines = [
        {key: value for key, value in row.items() if key not in {"id", "run_id", "position_id"}}
        for row in lines
    ]
    return {
        "pgn": game["pgn"],
        "color": color,
        "positions": [
            {"ply": row["ply"], "fen": row["fen"], "uci": row["uci"]} for row in positions
        ],
        "lines": clean_lines,
        "engine_config": config,
    }
