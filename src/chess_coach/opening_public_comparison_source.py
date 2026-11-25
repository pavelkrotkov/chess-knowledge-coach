"""Reconstruct the exact verified public source history for a candidate."""

import sqlite3

import chess

from .opening_context_replay import replay
from .opening_profile_lookup import guard
from .opening_storage import position_key


def board(index, item, budget):
    selected = item["selection"]
    source = item["source"]
    line = source["line"]
    recorded = source["source_history"]
    if (
        line["reference"] != selected["source"]["reference"]
        or line["moves"][0] != selected["move"]
        or recorded["prefix_sha256"] != selected["source"]["prefix_sha256"]
        or recorded["ply"] != selected["source"]["ply"]
    ):
        raise ValueError("public selection changed")
    db = sqlite3.connect(index.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(db, budget.expires)
        checked = replay(
            db,
            line["record"],
            recorded["ply"],
            selected["parent"],
            line,
            budget,
            include_prefix=True,
        )
    finally:
        db.close()
    prefix = checked.pop("prefix")
    if checked != recorded:
        raise ValueError("public history changed")
    result = chess.Board()
    for move in prefix:
        budget.check()
        result.push_uci(move)
    if position_key(result) != selected["parent"]:
        raise ValueError("public parent changed")
    return result
