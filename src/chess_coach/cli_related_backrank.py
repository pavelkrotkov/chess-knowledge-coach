"""CLI entry points for one selected back-rank attacking root."""

import json

from .related_backrank_attack import preview
from .related_backrank_defense import preview as defense_preview
from .related_backrank_defense import start_related as start_defense
from .related_backrank_source import roots
from .related_backrank_start import start_related


def configure(sub):
    listing = sub.add_parser("related-backrank-roots")
    listing.add_argument("--subject", required=True)
    listing.add_argument("--evidence", required=True, type=int)
    for name in ("related-backrank-attacks", "start-related-backrank-attack"):
        parser = sub.add_parser(name)
        parser.add_argument("--subject", required=True)
        parser.add_argument("--evidence", required=True, type=int)
        parser.add_argument("--corpus", required=True)
        parser.add_argument("--root", required=True)
        if name == "related-backrank-attacks":
            parser.add_argument("--cursor")
        else:
            parser.add_argument("--attempt", required=True)
            parser.add_argument("--reference", required=True)
    defense_commands(sub)


def defense_commands(sub):
    for name in ("related-backrank-defenses", "start-related-backrank-defense"):
        parser = sub.add_parser(name)
        parser.add_argument("--subject", required=True)
        parser.add_argument("--evidence", required=True, type=int)
        parser.add_argument("--corpus", required=True)
        if name == "related-backrank-defenses":
            parser.add_argument("--cursor")
        else:
            parser.add_argument("--attempt", required=True)
            parser.add_argument("--reference", required=True)


def defenses(db, args):
    print(
        json.dumps(
            defense_preview(db, args.subject, args.evidence, args.corpus, args.cursor), indent=2
        )
    )


def begin_defense(db, args):
    result = start_defense(
        db,
        attempt_id=args.attempt,
        subject=args.subject,
        evidence_id=args.evidence,
        corpus_version=args.corpus,
        reference=args.reference,
    )
    result.pop("source_key", None)
    print(json.dumps(result, indent=2))


def list_roots(db, args):
    evidence, _, _, choices = roots(db, args.subject, args.evidence)
    print(
        json.dumps(
            {
                "outcome": evidence["outcome"],
                "roots": [
                    {"move": root["move"]["uci"], "plies": root["distance_plies"]}
                    for root in choices
                ],
            },
            indent=2,
        )
    )


def listing(db, args):
    print(
        json.dumps(
            preview(db, args.subject, args.evidence, args.corpus, args.root, args.cursor), indent=2
        )
    )


def begin(db, args):
    result = start_related(
        db,
        attempt_id=args.attempt,
        subject=args.subject,
        evidence_id=args.evidence,
        corpus_version=args.corpus,
        root_move=args.root,
        reference=args.reference,
    )
    result.pop("source_key", None)
    print(json.dumps(result, indent=2))
