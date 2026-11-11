"""Verify the bounded first-turn sample and pinned opening catalog."""

from collections import Counter

from .classification_inputs import opening_graph
from .fact_fingerprint import canonical, digest
from .opening_snapshot import GRAPH_SHA256, SOURCE, VERSION
from .opening_storage import position_key


def catalog_dataset(db):
    row = db.connection.execute(
        "SELECT id FROM opening_datasets WHERE version=? AND source_url=? AND content_revision=1",
        (VERSION, SOURCE),
    ).fetchone()
    if row is None:
        raise ValueError("pinned catalog unavailable")
    dataset = row[0]
    for table, limit in (("opening_nodes", 10000), ("opening_edges", 100000)):
        if db.connection.execute(
            f"SELECT 1 FROM {table} WHERE dataset_id=? LIMIT 1 OFFSET ?", (dataset, limit)
        ).fetchone():
            raise ValueError("catalog exceeds bounds")
    if digest(canonical(opening_graph(db, dataset))) != GRAPH_SHA256:
        raise ValueError("pinned catalog differs")
    return dataset


def choices(db, dataset, board):
    rows = db.connection.execute(
        """SELECT e.uci,e.child_key,n.name,n.eco FROM opening_edges e
        JOIN opening_nodes n ON n.dataset_id=e.dataset_id AND n.position_key=e.child_key
        WHERE e.dataset_id=? AND e.parent_key=? ORDER BY e.uci,n.name LIMIT 100""",
        (dataset, position_key(board)),
    ).fetchall()
    result = {}
    for row in rows:
        try:
            move = board.parse_uci(row["uci"])
            after = board.copy()
            after.push(move)
            if position_key(after) == row["child_key"]:
                result.setdefault(row["uci"], {**dict(row), "san": board.san(move)})
        except (ValueError, TypeError):
            continue
    return list(result.values())


def common_black(black):
    if not black:
        return None, 0
    counts = Counter(first for first, _reply in black)
    first = min(counts, key=lambda move: (-counts[move], move))
    return first, counts[first]
