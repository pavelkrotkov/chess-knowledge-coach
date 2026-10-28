"""CLI commands for verified puzzle training."""

import json

from .puzzle_sessions import show_attempt, submit_move
from .training import create_training_item
from .training_feedback import puzzle_training_ref, show_training_puzzle, submit_training_move


def handle_create_puzzle_training(db, args):
    puzzle = db.connection.execute(
        """SELECT 1 FROM puzzles p JOIN puzzle_corpora c ON c.id = p.corpus_id
        WHERE c.version = ? AND p.puzzle_id = ?""",
        (args.version, args.puzzle_id),
    ).fetchone()
    if puzzle is None:
        raise ValueError("unknown versioned puzzle")
    item_id = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref(args.version, args.puzzle_id),
        skill=args.skill,
        operation=args.operation,
    )
    print(json.dumps({"id": item_id}, indent=2))


def handle_show_puzzle(db, args):
    if args.training_item_id is None:
        result = show_attempt(db, args.attempt_id)
    else:
        result = show_training_puzzle(db, args.attempt_id, item_id=args.training_item_id)
    print(json.dumps(result, indent=2))


def handle_play_puzzle(db, args):
    if (args.training_item_id is None) != (args.subject is None):
        raise ValueError("training item ID and subject must be provided together")
    if args.training_item_id is not None:
        result = submit_training_move(
            db,
            args.attempt_id,
            event_id=args.event_id,
            move=args.move,
            item_id=args.training_item_id,
            subject=args.subject,
        )
    else:
        result = submit_move(db, args.attempt_id, event_id=args.event_id, move=args.move)
    print(json.dumps(result, indent=2))
