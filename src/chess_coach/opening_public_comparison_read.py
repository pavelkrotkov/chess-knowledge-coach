"""Read only a current immutable source-bound public comparison."""

import sqlite3

from .fact_fingerprint import canonical, digest
from .opening_context_choice import token
from .opening_public_comparison_engine import configuration
from .opening_public_comparison_source import board
from .opening_public_comparison_view import view
from .opening_public_proof_files import latest
from .tactical_study_path import planning

VERSION = "opening-context-public-comparison-v1"


def key(selection):
    fields = ("color", "parent", "path", "move", "child")
    return digest(canonical([VERSION, {name: selection[name] for name in fields}]))


def lookup(root, subject, item, index, budget):
    directory, _ = planning(root, subject)
    selection = item["selection"]
    try:
        payload = latest(directory, key(selection))
        if payload is None:
            return {"status": "unavailable" if item["source"] is None else "unmeasured"}
        if payload["version"] != VERSION or payload["selection"] != selection:
            return {"status": "stale"}
        public_board = board(index, item, budget)
        _, config = configuration(payload["configuration"]["engine_path"], public_board)
        budget.check()
        if config != payload["configuration"]:
            return {"status": "stale"}
        return view(payload, public_board)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        return {"status": "stale"}


def enrich(root, subject, items, index, budget):
    for item in items:
        item["selection_token"] = token(item["selection"])
        item["comparison"] = lookup(root, subject, item, index, budget)
