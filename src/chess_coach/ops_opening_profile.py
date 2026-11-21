"""Report a private opening profile without initializing the database."""

import argparse
import json
import os
from pathlib import Path

from .opening_profile_cli_report import report


def main():
    parser = argparse.ArgumentParser(description="Read a private, source-matched opening profile")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--game-id", required=True, type=int)
    parser.add_argument("--position-id", required=True, type=int)
    parser.add_argument("--alternative", required=True)
    parser.add_argument("--reference", choices=("broadcast", "recent"), default="broadcast")
    args = parser.parse_args()
    try:
        value = report(
            args.project_root,
            os.environ["CHESS_SUBJECT"],
            args.game_id,
            args.position_id,
            args.alternative,
            args.reference,
        )
    except Exception:
        raise SystemExit("Opening profile unavailable.") from None
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
