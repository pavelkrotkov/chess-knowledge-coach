"""CLI entry points for manual bounded selection and inspection."""

import json
import os

from .deep_selection import select_deep
from .deep_selection_views import list_selections, show_selection


def configure(sub):
    select = sub.add_parser("select-deep", help="Select bounded decisions for later deep analysis")
    select.add_argument("--game-id", action="append", type=int, required=True)
    select.add_argument("--per-game", type=int, default=4)
    select.add_argument("--total", type=int, default=12)
    select.add_argument("--cp-gap", type=int, default=150)
    select.add_argument("--wdl-gap", type=float, default=0.1)
    show = sub.add_parser(
        "show-deep-selection", help="Inspect a selection without running analysis"
    )
    show.add_argument("game_id", type=int)
    show.add_argument("--selection-id", type=int)
    sub.add_parser("list-deep-selections", help="List the learner's current selections")


def _learner():
    learner = os.environ.get("LICHESS_USERNAME")
    if not learner:
        raise ValueError("LICHESS_USERNAME is required")
    return learner


def handle_select(db, args):
    report = select_deep(
        db,
        args.game_id,
        learner=_learner(),
        per_game=args.per_game,
        total=args.total,
        cp_gap=args.cp_gap,
        wdl_gap=args.wdl_gap,
    )
    print(json.dumps(report, indent=2))


def handle_show(db, args):
    print(
        json.dumps(
            show_selection(db, args.game_id, _learner(), selection_id=args.selection_id), indent=2
        )
    )


def handle_list(db, args):
    print(json.dumps(list_selections(db, _learner()), indent=2))
