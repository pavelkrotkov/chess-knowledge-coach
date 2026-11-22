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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--preparation", action="store_true", help="Inventory this checked experiment"
    )
    mode.add_argument(
        "--prepare-public",
        action="store_true",
        help="Prepare bounded recent public capture evidence",
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
            value = prepare_public(*arguments)
        elif args.preparation:
            value = preparation(*arguments)
        else:
            value = report(*arguments, args.reference)
    except Exception:
        raise SystemExit("Opening profile unavailable.") from None
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
