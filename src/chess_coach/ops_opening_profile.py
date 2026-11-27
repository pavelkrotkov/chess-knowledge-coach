"""Report a private opening profile without initializing the database."""

import argparse
import json
import os
from pathlib import Path

from .opening_profile_cli_report import preparation, prepare_public, report


def main():
    parser = argparse.ArgumentParser(description="Read a private, source-matched opening profile")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--game-id", required=True, type=int)
    parser.add_argument("--position-id", required=True, type=int)
    parser.add_argument("--alternative", required=True)
    parser.add_argument("--reference", choices=("broadcast", "recent"), default="broadcast")
    parser.add_argument("--fork-window", choices=("initial", "continuation"), default="initial")
    parser.add_argument(
        "--proof-kind", choices=("fork", "prevention", "protection", "capture_pv"), default="fork"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--preparation", action="store_true", help="Inventory this checked experiment"
    )
    mode.add_argument(
        "--prepare-public",
        dest="prepare_public",
        action="store_const",
        const="capture",
        help="Prepare bounded recent public capture evidence",
    )
    mode.add_argument(
        "--prepare-public-forks",
        dest="prepare_public",
        action="store_const",
        const="fork",
        help="Prepare bounded recent public capture and fork evidence",
    )
    mode.add_argument(
        "--prepare-public-prevention",
        dest="prepare_public",
        action="store_const",
        const="prevention",
        help="Prepare bounded recent public knight-fork prevention evidence",
    )
    mode.add_argument(
        "--prepare-public-protection",
        dest="prepare_public",
        action="store_const",
        const="protection",
        help="Prepare bounded public named-piece protection evidence",
    )
    mode.add_argument(
        "--prepare-public-capture-pv",
        dest="prepare_public",
        action="store_const",
        const="capture_pv",
        help="Prepare bounded public capture consequences",
    )
    mode.add_argument(
        "--recommendation-course", action="store_true", help="Read a source-bound selected revision"
    )
    args = parser.parse_args()
    try:
        arguments = (
            args.project_root,
            os.environ["CHESS_SUBJECT"],
            args.game_id,
            args.position_id,
            args.alternative,
        )
        if args.prepare_public:
            if args.reference != "recent":
                raise ValueError("recent reference required")
            value = prepare_public(
                *arguments,
                forks=args.prepare_public == "fork",
                fork_window=args.fork_window,
                prevent=args.prepare_public == "prevention",
                protection=args.prepare_public == "protection",
                capture_pv=args.prepare_public == "capture_pv",
            )
        elif args.recommendation_course:
            from .opening_recommendation_cli import report as recommendation

            value = recommendation(*arguments)
        elif args.preparation:
            value = preparation(*arguments)
        else:
            value = report(
                *arguments, args.reference, fork_window=args.fork_window, proof_kind=args.proof_kind
            )
    except Exception:
        raise SystemExit("Opening profile unavailable.") from None
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
