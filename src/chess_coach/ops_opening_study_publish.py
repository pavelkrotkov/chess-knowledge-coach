"""Publish one explicitly reviewed current opening course privately."""

import argparse
from pathlib import Path

from .opening_study_reconcile import reconcile_locked
from .opening_study_session import publish_locked
from .opening_unfamiliar_study import publish_locked as publish_unfamiliar
from .tactical_course_deadline import PreviewDeadline


def _run(args):
    if args.reconcile_only:
        return reconcile_locked(args.project_root, args.preview_version)
    if args.unfamiliar:
        return publish_unfamiliar(args.project_root, args.preview_version)
    return publish_locked(
        args.project_root, args.game_id, args.position_id, args.alternative, args.preview_version
    )


def _validate(args, parser):
    values = (args.game_id, args.position_id, args.alternative)
    if args.unfamiliar and any(value is not None for value in values):
        parser.error("unfamiliar publication does not take a game, position or alternative")
    if not args.reconcile_only and not args.unfamiliar and any(value is None for value in values):
        parser.error("publication requires --game-id, --position-id and --alternative")


def main():
    parser = argparse.ArgumentParser(description="Publish a reviewed private opening Study")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--reconcile-only", action="store_true")
    parser.add_argument("--unfamiliar", action="store_true")
    parser.add_argument("--game-id", type=int)
    parser.add_argument("--position-id", type=int)
    parser.add_argument("--alternative")
    parser.add_argument("--preview-version", required=True)
    args = parser.parse_args()
    _validate(args, parser)
    try:
        _run(args)
    except (Exception, PreviewDeadline):
        raise SystemExit(
            "Opening Study publication incomplete; retain the private intent."
        ) from None
    print(
        "Private opening Study destination reconciled."
        if args.reconcile_only
        else "Private opening Study verified."
    )


if __name__ == "__main__":
    main()
