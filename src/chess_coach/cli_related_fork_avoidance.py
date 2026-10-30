"""CLI entry to created-fork avoidance previews and sessions."""

import json

from .related_fork_avoidance import preview
from .related_fork_avoidance_start import start_related


def configure(sub):
    listing = sub.add_parser("related-fork-avoidances")
    listing.add_argument("--subject", required=True)
    listing.add_argument("--evidence", required=True, type=int)
    listing.add_argument("--corpus", required=True)
    listing.add_argument("--cursor")
    begin = sub.add_parser("start-related-fork-avoidance")
    begin.add_argument("--subject", required=True)
    begin.add_argument("--evidence", required=True, type=int)
    begin.add_argument("--corpus", required=True)
    begin.add_argument("--attempt", required=True)
    begin.add_argument("--reference", required=True)


def listing(db, args):
    print(json.dumps(preview(db, args.subject, args.evidence, args.corpus, args.cursor), indent=2))


def begin(db, args):
    result = start_related(
        db,
        attempt_id=args.attempt,
        subject=args.subject,
        evidence_id=args.evidence,
        corpus_version=args.corpus,
        reference=args.reference,
    )
    result.pop("source_key", None)
    print(json.dumps(result, indent=2))


COMMANDS = {"related-fork-avoidances": listing, "start-related-fork-avoidance": begin}
