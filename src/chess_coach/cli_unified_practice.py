"""Command-line entry points for generic practice sessions."""

import json

from .objective_pin_list import candidates as pin_candidates
from .objective_publication import cancel as cancel_objective
from .objective_status import inspect as inspect_objective
from .objective_worker import process as process_objectives
from .pawn_practice_list import list_candidates as list_pawn_candidates
from .unified_own_game import list_candidates
from .unified_session_events import hint, show, submit
from .unified_sessions import start


def configure(sub):
    listing = sub.add_parser("list-own-game-practice")
    listing.add_argument("--subject", required=True)
    pin = sub.add_parser("list-pin-practice")
    pin.add_argument("--subject", required=True)
    pawn = sub.add_parser("list-pawn-practice")
    pawn.add_argument("--subject", required=True)
    pawn.add_argument("--before")
    verify = sub.add_parser("process-objective-verifications")
    verify.add_argument("--subject", required=True)
    verify.add_argument("--limit", type=int, default=4)
    for name in ("show-objective-verification", "cancel-objective-verification"):
        action = sub.add_parser(name)
        action.add_argument("--subject", required=True)
        action.add_argument("--attempt", required=True)
        action.add_argument("--event", required=True)
    begin = sub.add_parser("start-unified")
    begin.add_argument("--attempt", required=True)
    begin.add_argument("--subject", required=True)
    begin.add_argument("--source", required=True, choices=("corpus", "public", "own-game"))
    begin.add_argument("--version", required=True)
    begin.add_argument("--key", required=True)
    for name in ("show-unified", "move-unified", "hint-unified"):
        parser = sub.add_parser(name)
        parser.add_argument("--attempt", required=True)
        parser.add_argument("--subject", required=True)
        if name != "show-unified":
            parser.add_argument("--event", required=True)
        if name == "move-unified":
            parser.add_argument("--move", required=True)


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
            ),
            indent=2,
        )
    )


def handle_show(db, args):
    print(json.dumps(show(db, args.attempt, args.subject), indent=2))


def handle_move(db, args):
    print(
        json.dumps(
            submit(db, args.attempt, args.subject, event_id=args.event, move=args.move), indent=2
        )
    )


def handle_hint(db, args):
    print(json.dumps(hint(db, args.attempt, args.subject, event_id=args.event), indent=2))


def handle_list(db, args):
    print(json.dumps(list_candidates(db, args.subject), indent=2))


def handle_list_pin(db, args):
    print(json.dumps(pin_candidates(db, args.subject), indent=2))


def handle_list_pawn(db, args):
    print(
        json.dumps(
            list_pawn_candidates(db, args.subject, before=getattr(args, "before", None)), indent=2
        )
    )


def handle_verify(db, args):
    print(json.dumps(process_objectives(db, args.subject, limit=args.limit), indent=2))


def handle_verify_status(db, args):
    print(json.dumps(inspect_objective(db, args.subject, args.attempt, args.event), indent=2))


def handle_verify_cancel(db, args):
    cancel_objective(db, args.subject, args.attempt, args.event)
    print(json.dumps(inspect_objective(db, args.subject, args.attempt, args.event), indent=2))
