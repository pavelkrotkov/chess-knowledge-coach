"""CLI enrollment and recovery for qualified unified mate learning."""

import json

from .unified_sessions import start


def configure(sub, begin):
    begin.add_argument("--training", action="store_true")
    begin.add_argument("--training-item-id", type=int)
    complete = sub.add_parser("complete-unified-learning")
    complete.add_argument("--attempt", required=True)
    complete.add_argument("--subject", required=True)


def handle_complete_learning(db, args):
    from .unified_training_complete import complete

    print(json.dumps(complete(db, args.attempt, args.subject), indent=2))


def options(args):
    return {
        "training": getattr(args, "training", False),
        "item_id": getattr(args, "training_item_id", None),
    }


def handle_start(db, args):
    print(
        json.dumps(
            start(
                db,
                attempt_id=args.attempt,
                subject=args.subject,
                source_type=args.source,
                version=args.version,
                key=args.key,
                goal=getattr(args, "goal", None),
                **options(args),
            ),
            indent=2,
        )
    )
