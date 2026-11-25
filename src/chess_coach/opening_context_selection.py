"""Bind an exact context selection to its checked public occurrence."""

from .opening_storage import position_key
from .opening_unfamiliar_sources import choices


def catalog_options(db, dataset, board):
    options = choices(db, dataset, board)
    more = (
        db.connection.execute(
            "SELECT 1 FROM opening_edges e JOIN opening_nodes n ON n.dataset_id=e.dataset_id "
            "AND n.position_key=e.child_key WHERE e.dataset_id=? AND e.parent_key=? LIMIT 1 OFFSET 100",
            (dataset, position_key(board)),
        ).fetchone()
        is not None
    )
    return options, more


def selection(color, parent, path, item, source):
    occurrence = None
    if source is not None:
        occurrence = {
            "reference": source["line"]["reference"],
            "ply": source["source_history"]["ply"],
            "prefix_sha256": source["source_history"]["prefix_sha256"],
        }
    return {
        "version": "opening-context-selection-v1",
        "color": color,
        "parent": parent,
        "path": list(path),
        "move": item["uci"],
        "child": item["child_key"],
        "source": occurrence,
    }
