"""Private operator commands for bounded snapshot acquisition."""

import json
from pathlib import Path

from .puzzle_snapshot import acquire
from .puzzle_snapshot_limits import Limits
from .puzzle_snapshot_state import statuses


def configure(sub):
    download = sub.add_parser(
        "acquire-puzzles", help="Download and decode the official puzzle snapshot"
    )
    download.add_argument("--project-root", type=Path, required=True)
    download.add_argument("--version", required=True)
    download.add_argument("--max-archive-bytes", type=int, required=True)
    download.add_argument("--max-csv-bytes", type=int, required=True)
    download.add_argument("--reserve-bytes", type=int, required=True)
    download.add_argument("--seconds", type=float, required=True)
    download.add_argument("--connect-timeout", type=float, default=10)
    download.add_argument("--read-timeout", type=float, default=30)
    status = sub.add_parser("acquisition-status", help="Show local acquisition progress")
    status.add_argument("--project-root", type=Path, required=True)


def _acquire(args):
    limits = Limits(
        args.max_archive_bytes,
        args.max_csv_bytes,
        args.reserve_bytes,
        args.seconds,
        args.connect_timeout,
        args.read_timeout,
    )
    print(json.dumps(acquire(args.project_root, args.version, limits), indent=2))


def _status(args):
    print(json.dumps(statuses(args.project_root), indent=2))


COMMANDS = {"acquire-puzzles": _acquire, "acquisition-status": _status}
