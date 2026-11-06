"""Explicitly import the pinned local public broadcast sample."""

import argparse
import os
from pathlib import Path

from .opening_reference_index import build


def main():
    parser = argparse.ArgumentParser(description="Prepare a bounded opening reference sample")
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    coverage = build(args.project_root, os.environ["CHESS_SUBJECT"])
    print("Reference sample prepared:", coverage)


if __name__ == "__main__":
    main()
