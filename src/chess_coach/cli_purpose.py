"""Explicit private diagnostic requests, execution and inspection."""

import json
import os

from .purpose_request import create
from .purpose_view import show
from .purpose_worker import run


def configure(sub):
    request = sub.add_parser("request-purpose", help="Request one owned candidate-set diagnostic")
    request.add_argument("position_id", type=int)
    request.add_argument("--engine-path", default="/usr/games/stockfish")
    worker = sub.add_parser("run-purpose", help="Run one explicitly requested bounded diagnostic")
    worker.add_argument("request_id", type=int)
    worker.add_argument("--retry", action="store_true")
    inspect = sub.add_parser("show-purpose", help="Inspect an owned diagnostic without searching")
    inspect.add_argument("request_id", type=int)


def _learner():
    learner = os.environ.get("LICHESS_USERNAME")
    if not learner:
        raise ValueError("LICHESS_USERNAME is required")
    return learner


def handle_create(db, args):
    print(
        json.dumps(create(db, args.position_id, _learner(), engine_path=args.engine_path), indent=2)
    )


def handle_run(db, args):
    print(json.dumps(run(db, args.request_id, _learner(), retry=args.retry), indent=2))


def handle_show(db, args):
    print(json.dumps(show(db, args.request_id, _learner()), indent=2))
