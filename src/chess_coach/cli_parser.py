"""Build the command-line parser."""

import argparse

from .cli_args_datasets import configure as datasets
from .cli_args_games import configure as games
from .cli_args_learning import configure as learning
from .cli_args_pipeline import configure as pipeline
from .cli_recovery import configure as recovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first chess knowledge coach")
    parser.add_argument("--db", default="coach.sqlite", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    games(sub)
    datasets(sub)
    learning(sub)
    pipeline(sub)
    recovery(sub)
    sub.add_parser("capabilities", help="Report versioned product capabilities")
    sub.add_parser("competencies", help="Report competency coverage and prerequisites")
    sub.add_parser("seed-competencies", help="Store the current competency graph version")
    return parser
