"""Bounded played moves and last reached named position."""


def _match(positions, opening):
    key = opening["position_key"] if opening else None
    if not key:
        return None
    matches = [p for p in positions if key == " ".join(p["fen"].split()[:4])]
    return matches[-1] if matches else None


def position_data(db, game_id, opening):
    positions = db.connection.execute(
        "SELECT id,ply,fen,san FROM positions WHERE game_id=? ORDER BY ply LIMIT 1001", (game_id,)
    ).fetchall()
    truncated = len(positions) > 1000
    positions = positions[:1000]
    match = _match(positions, opening)
    ply = match["ply"] if match else 0
    return {
        "position_id": match["id"] if match else None,
        "ply": ply or None,
        "line": [p["san"] for p in positions if p["ply"] <= ply],
        "moves": [{"id": p["id"], "ply": p["ply"], "san": p["san"]} for p in positions],
        "opening_positions": _opening_positions(positions, ply),
        "positions_truncated": truncated,
    }


def _opening_positions(positions, ply):
    moves = []
    output = []
    for position in positions:
        if position["ply"] > ply:
            break
        moves.append(position["san"])
        output.append(
            {
                "key": " ".join(position["fen"].split()[:4]),
                "line": " ".join(moves),
                "id": position["id"],
            }
        )
    return output
