"""Handlers for learning commands."""

import json

from .evidence import evidence_report, validate_evidence
from .mastery import mastery_report, update_mastery
from .training import create_training_item, due_items, review_item


def handle_validate_evidence(db, args):
    validate_evidence(db, args.evidence_id)
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
