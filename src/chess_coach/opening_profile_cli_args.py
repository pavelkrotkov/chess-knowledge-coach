"""Parse the existing private opening-profile command grammar."""

import argparse
from pathlib import Path


def parse():
    parser = argparse.ArgumentParser(description="Read a private, source-matched opening profile")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--game-id", required=True, type=int)
    parser.add_argument("--position-id", required=True, type=int)
    parser.add_argument("--alternative", required=True)
    parser.add_argument("--reference", choices=("broadcast", "recent"), default="broadcast")
    parser.add_argument("--fork-window", choices=("initial", "continuation"), default="initial")
    parser.add_argument(
        "--proof-kind",
        choices=(
            "fork",
            "prevention",
            "protection",
            "capture_pv",
            "defense_pv",
            "mate",
            "short_mate",
            "back_rank",
        ),
        default="fork",
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
        help="Prepare bounded recent public capture or selected mate evidence",
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
        "--prepare-public-defense-pv",
        dest="prepare_public",
        action="store_const",
        const="defense_pv",
        help="Prepare bounded public defense consequences",
    )
    mode.add_argument(
        "--recommendation-course", action="store_true", help="Read a source-bound selected revision"
    )
    return parser.parse_args()
