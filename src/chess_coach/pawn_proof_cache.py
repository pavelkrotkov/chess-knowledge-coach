"""Bounded copy-safe reuse of locally verified pawn proof reports."""

import json
from collections import OrderedDict
from threading import Lock

_LIMIT = 32
_reports = OrderedDict()
_lock = Lock()


def key(board, version, manifest, node_limit, max_plies):
    return (
        board.root().fen(en_passant="fen", promoted=True),
        tuple(move.uci() for move in board.move_stack),
        board.fen(en_passant="fen", promoted=True),
        board.chess960,
        version,
        manifest,
        node_limit,
        max_plies,
    )


def get(proof_key):
    with _lock:
        value = _reports.get(proof_key)
        if value is not None:
            _reports.move_to_end(proof_key)
    return json.loads(value) if value is not None else None


def put(proof_key, result):
    value = json.dumps(result, sort_keys=True, separators=(",", ":"))
    with _lock:
        _reports[proof_key] = value
        _reports.move_to_end(proof_key)
        if len(_reports) > _LIMIT:
            _reports.popitem(last=False)


def proof(board, tablebase, node_limit, max_plies, reuse, version, manifest, report, describe):
    proof_key = key(board, version, manifest, node_limit, max_plies)
    cached = get(proof_key) if reuse else None
    if cached is not None:
        return cached
    result = report(board, tablebase, node_limit, max_plies)
    result["geometry"] = describe(board)
    if reuse:
        put(proof_key, result)
    return result
