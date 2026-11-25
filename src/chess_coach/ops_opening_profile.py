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
    parser.add_argument("--proof-kind", choices=("fork", "prevention"), default="fork")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--preparation", action="store_true", help="Inventory this checked experiment"
    )
    mode.add_argument(
        "--prepare-public",
        action="store_true",
        help="Prepare bounded recent public capture evidence",
    )
    mode.add_argument(
        "--prepare-public-forks",
        action="store_true",
        help="Prepare bounded recent public capture and fork evidence",
    )
    mode.add_argument(
        "--prepare-public-prevention",
        action="store_true",
        help="Prepare bounded recent public knight-fork prevention evidence",
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
        if args.prepare_public or args.prepare_public_forks or args.prepare_public_prevention:
            if args.reference != "recent":
                raise ValueError("recent reference required")
            value = prepare_public(
                *arguments,
                forks=args.prepare_public_forks,
                fork_window=args.fork_window,
                prevent=args.prepare_public_prevention,
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
