"""CLI entry point for a bounded, manually invoked deep worker."""

import json
import os

from .deep_execution_config import DeepOptions
from .deep_execution_worker import run_deep


def configure(sub):
    parser = sub.add_parser("run-deep", help="Run bounded deep analysis on a current selection")
    parser.add_argument("selection_id", type=int)
    parser.add_argument("--engine-path", default="/usr/games/stockfish")
    parser.add_argument("--nodes", type=int, default=50000)
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--multipv", type=int, default=3)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--min-depth", type=int, default=4)
    parser.add_argument("--max-jobs", type=int, default=4)
    parser.add_argument("--retry-insufficient", action="store_true")


def handle_run(db, args):
    learner = os.environ.get("LICHESS_USERNAME")
    if not learner:
        raise ValueError("LICHESS_USERNAME is required")
    options = DeepOptions(
        engine_path=args.engine_path,
        nodes=args.nodes,
        seconds=args.seconds,
        multipv=args.multipv,
        threads=args.threads,
        hash_mb=args.hash_mb,
        min_depth=args.min_depth,
        max_jobs=args.max_jobs,
        retry_insufficient=args.retry_insufficient,
    )
    print(json.dumps(run_deep(db, args.selection_id, learner=learner, options=options), indent=2))
