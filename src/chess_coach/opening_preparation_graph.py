"""Inventory the two checked opening prefixes without claiming a full tree."""

from .fact_fingerprint import canonical, digest
from .opening_storage import position_key


def _key(value):
    return digest(canonical(value))


def _branch(board, line):
    replay = board.copy()
    positions = [_key(position_key(replay))]
    edges = []
    for text in line["uci"].split():
        parent = position_key(replay)
        move = replay.parse_uci(text)
        replay.push(move)
        child = position_key(replay)
        edges.append(_key([parent, move.uci(), child]))
        positions.append(_key(child))
    return {"positions": positions, "edges": edges, "plies": len(edges)}


def graph(board, experiment):
    played = _branch(board, experiment["played"])
    alternative = _branch(board, experiment["alternative"])
    positions = [set(item["positions"]) for item in (played, alternative)]
    edges = [set(item["edges"]) for item in (played, alternative)]
    return {
        "played": played,
        "alternative": alternative,
        "unique_positions": len(positions[0] | positions[1]),
        "unique_edges": len(edges[0] | edges[1]),
        "shared_positions": len(positions[0] & positions[1]),
        "shared_edges": len(edges[0] & edges[1]),
        "played_only_positions": len(positions[0] - positions[1]),
        "alternative_only_positions": len(positions[1] - positions[0]),
        "played_only_edges": len(edges[0] - edges[1]),
        "alternative_only_edges": len(edges[1] - edges[0]),
    }
