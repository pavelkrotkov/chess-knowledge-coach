"""Build a bounded public response DAG for one exact candidate root."""

import json
import sqlite3

from .opening_distance_branch import branch, records
from .opening_distance_compare import counts
from .opening_distance_history import description
from .opening_distance_partition import partitions, transpositions
from .opening_profile_lookup import MAX_GAMES, guard

VERSION = "opening-switching-distance-v1"
BRANCH_PLIES = 4


def _tree(db, rows, parent, move, budget):
    graphs, provenance, incomplete = [], [], 0
    for record, first in rows:
        budget.check()
        try:
            value = branch(db, record, first, parent, move, budget)
            if value is None:
                incomplete += 1
                continue
            graph, source = value
            graphs.append(graph)
            provenance.append(source)
        except (ValueError, TypeError, IndexError, KeyError, json.JSONDecodeError):
            incomplete += 1
    return graphs, provenance, incomplete


def distance(index, selection, history, budget):
    db = sqlite3.connect(index.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, budget.expires)
        rows = records(db, selection["parent"], selection["move"])
        graphs, sources, incomplete = _tree(
            db, rows[:MAX_GAMES], selection["parent"], selection["move"], budget
        )
        return {
            "version": VERSION,
            "status": (
                "unavailable"
                if not graphs
                else "incomplete"
                if incomplete or len(rows) > MAX_GAMES
                else "checked"
            ),
            "selection": selection,
            "source_index_sha256": selection["reference_index_sha256"],
            "source_filter": "broadcast exact parent and candidate move",
            "limits": {"games": MAX_GAMES, "branch_plies": BRANCH_PLIES},
            "selected_games": min(len(rows), MAX_GAMES),
            "checked_games": len(graphs),
            "omitted_games": incomplete,
            "more_games": len(rows) > MAX_GAMES,
            "branches": len({tuple(graph["edges"]) for graph in graphs}),
            "transpositions": transpositions(graphs),
            "branch_partition": partitions(graphs, history),
            "source_records": sources,
            "history": description(history),
            "counts": counts(graphs, history) if graphs else None,
        }
    finally:
        db.close()
