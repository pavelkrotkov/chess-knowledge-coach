"""Handlers for learning commands."""

import json

from .evidence import evidence_report, validate_evidence
from .evidence_review import inspect_evidence, list_evidence, review_evidence
from .mastery import mastery_report, update_mastery
from .puzzle_sessions import request_hint, show_attempt, start_attempt, submit_move
from .training import create_training_item, due_items, review_item


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
    print(
        json.dumps(
            submit_move(db, args.attempt_id, event_id=args.event_id, move=args.move), indent=2
        )
    )


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
