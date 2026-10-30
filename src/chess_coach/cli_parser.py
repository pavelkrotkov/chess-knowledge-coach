"""Build the command-line parser."""

import argparse

from .cli_args_datasets import configure as datasets
from .cli_args_games import configure as games
from .cli_args_learning import configure as learning
from .cli_args_pipeline import configure as pipeline
from .cli_deep_execution import configure as deep_execution
from .cli_deep_selection import configure as deep_selection
from .cli_public_training import configure as public_training
from .cli_purpose import configure as purpose
from .cli_recovery import configure as recovery
from .cli_recurrence import configure as recurrence
from .cli_related_capture import configure as related_capture
from .cli_related_fork import configure as related_fork
from .cli_related_fork_prevention import configure as related_fork_prevention
from .cli_related_protection import configure as related_protection
from .cli_snapshot import configure as snapshot
from .cli_unified_practice import configure as unified_practice


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first chess knowledge coach")
    parser.add_argument("--db", default="coach.sqlite", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    games(sub)
    datasets(sub)
    learning(sub)
    recurrence(sub)
    pipeline(sub)
    recovery(sub)
    deep_selection(sub)
    snapshot(sub)
    deep_execution(sub)
    public_training(sub)
    purpose(sub)
    unified_practice(sub)
    related_capture(sub)
    related_fork(sub)
    related_fork_prevention(sub)
    related_protection(sub)
    sub.add_parser("capabilities", help="Report versioned product capabilities")
    sub.add_parser("competencies", help="Report competency coverage and prerequisites")
    sub.add_parser("seed-competencies", help="Store the current competency graph version")
    return parser
