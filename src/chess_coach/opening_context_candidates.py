"""Check a bounded set of catalog choices for one exact parent."""

import sqlite3

import chess

from .opening_context_public import checked, recorded
from .opening_context_selection import catalog_options, selection
from .opening_storage import position_key

CHOICES_PER_PARENT = 2


def _board(parent, path):
    board = chess.Board()
    for uci in path:
        board.push_uci(uci)
    if position_key(board) != parent:
        raise ValueError("opening parent differs")
    return board


def choices(db, root, subject, dataset, color, parent, path, seen, incomplete, budget, index):
    board = _board(parent, path)
    with budget.scope(snapshot=True):
        options, more = catalog_options(db, dataset, board)
    matches = recorded(index, parent, options, budget)
    options.sort(
        key=lambda item: (
            item["uci"] not in matches,
            (color, parent, item["uci"]) in seen,
            item["uci"],
        )
    )
    selected = options[:CHOICES_PER_PARENT]
    items = []
    for item in selected:
        budget.check()
        if (color, parent, item["uci"]) in seen:
            status = "seen_in_checked_sample"
        else:
            status = "not_seen_in_checked_sample"
        try:
            source = checked(root, subject, parent, item, budget, index)
        except (OSError, ValueError, sqlite3.Error):
            source = None
        items.append(
            {
                **item,
                "selection": selection(color, parent, path, item, source),
                "history": status,
                "history_incomplete": incomplete,
                "source": source,
            }
        )
    return {
        "items": items,
        "catalog_screened": len(options),
        "catalog_screen_limit": 100,
        "omitted_screened": max(0, len(options) - CHOICES_PER_PARENT),
        "screen_incomplete": more,
        "truncated": len(options) > CHOICES_PER_PARENT or more,
    }
