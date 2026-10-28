"""Handlers for learning commands."""

import json

from .evidence import evidence_report, validate_evidence
from .evidence_review import inspect_evidence, list_evidence, review_evidence
from .mastery import mastery_report, update_mastery
from .puzzle_sessions import request_hint, show_attempt, start_attempt, submit_move
from .training import create_training_item, due_items, review_item
from .training_feedback import puzzle_training_ref, submit_training_move


def handle_validate_evidence(db, args):
    validate_evidence(db, args.evidence_id, actor=args.actor)
    print(json.dumps({"validated": args.evidence_id}, indent=2))


def handle_update_mastery(db, args):
    print(
        json.dumps(
            update_mastery(db, skill=args.skill, operation=args.operation, subject=args.subject),
            indent=2,
        )
    )


def handle_mastery_report(db, args):
    print(json.dumps(mastery_report(db, subject=args.subject), indent=2))


def handle_create_training(db, args):
    print(
        json.dumps(
            {
                "id": create_training_item(
                    db,
                    source_type=args.source_type,
                    source_ref=args.source_ref,
                    skill=args.skill,
                    operation=args.operation,
                )
            },
            indent=2,
        )
    )


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


def handle_due_training(db, args):
    print(json.dumps(due_items(db, limit=args.limit), indent=2, default=str))


def handle_review_training(db, args):
    print(
        json.dumps(
            review_item(db, args.item_id, args.rating, elapsed_seconds=args.elapsed_seconds),
            indent=2,
        )
    )


def handle_evidence_report(db, args):
    print(json.dumps(evidence_report(db), indent=2))


def handle_start_puzzle(db, args):
    print(
        json.dumps(
            start_attempt(
                db, attempt_id=args.attempt_id, version=args.version, puzzle_id=args.puzzle_id
            ),
            indent=2,
        )
    )


def handle_show_puzzle(db, args):
    print(json.dumps(show_attempt(db, args.attempt_id), indent=2))


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


def handle_hint_puzzle(db, args):
    print(json.dumps(request_hint(db, args.attempt_id, event_id=args.event_id), indent=2))


def handle_list_evidence(db, args):
    print(json.dumps(list_evidence(db, after_id=args.after_id, limit=args.limit), indent=2))


def handle_inspect_evidence(db, args):
    print(json.dumps(inspect_evidence(db, args.evidence_id), indent=2))


def handle_review_evidence(db, args):
    print(
        json.dumps(
            review_evidence(
                db,
                args.evidence_id,
                decision=args.decision,
                actor=args.actor,
                rationale=args.rationale,
            ),
            indent=2,
        )
    )
