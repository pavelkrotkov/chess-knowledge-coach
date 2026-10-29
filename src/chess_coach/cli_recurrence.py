"""Command-line access to bounded recurrence candidates."""

import json

from .recurrence_report import default_windows, report


def configure(sub):
    parser = sub.add_parser("recurrence", help="Compare bounded recurring-pattern candidates")
    parser.add_argument("--learner", required=True)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--compare-start")


def handle(db, args):
    defaults = default_windows()
    start, end, previous = (
        args.start or defaults[0],
        args.end or defaults[1],
        args.compare_start or defaults[2],
    )
    print(json.dumps(report(db, args.learner, start, end, previous), indent=2))
