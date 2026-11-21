"""Explicitly acquire or index one bounded public rated-game prefix."""

import argparse
import os
from pathlib import Path

from .opening_recent_acquire import acquire
from .opening_recent_index import build


def main():
    parser = argparse.ArgumentParser(description="Prepare a bounded recent rated-game sample")
    parser.add_argument("action", choices=("acquire", "build"))
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    action = acquire if args.action == "acquire" else build
    result = action(args.project_root, os.environ["CHESS_SUBJECT"])
    print("Recent reference", args.action, "completed:", result)


if __name__ == "__main__":
    main()
