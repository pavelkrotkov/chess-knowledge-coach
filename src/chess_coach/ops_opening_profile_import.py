"""Explicitly build the separate pinned ordered public profile index."""

import argparse
import os
from pathlib import Path

from .opening_profile_index import build


def main():
    parser = argparse.ArgumentParser(description="Prepare a bounded ordered opening profile sample")
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    coverage = build(args.project_root, os.environ["CHESS_SUBJECT"])
    print("Ordered reference sample prepared:", coverage)


if __name__ == "__main__":
    main()
