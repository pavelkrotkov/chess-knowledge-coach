"""Explicitly prepare the context-preserving public opening index."""

import argparse
import os
from pathlib import Path

from .opening_fit_context_index import build


def main():
    parser = argparse.ArgumentParser(description="Prepare opening context sample")
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    coverage = build(args.project_root, os.environ["CHESS_SUBJECT"])
    print("Opening context sample prepared:", coverage)


if __name__ == "__main__":
    main()
