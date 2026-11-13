"""Command-line pin previews and source-bound transfer sessions."""

import json

from .related_pin import preview
from .related_pin_start import start_related


def configure(sub):
    listing = sub.add_parser("related-pins")
    listing.add_argument("--subject", required=True)
    listing.add_argument("--evidence", required=True, type=int)
    listing.add_argument("--corpus", required=True)
    listing.add_argument("--cursor")
    listing.add_argument("--mechanism", choices=("slide",))
    begin = sub.add_parser("start-related-pin")
    begin.add_argument("--subject", required=True)
    begin.add_argument("--evidence", required=True, type=int)
    begin.add_argument("--corpus", required=True)
    begin.add_argument("--attempt", required=True)
    begin.add_argument("--reference", required=True)
    begin.add_argument("--mechanism", choices=("slide",))


def listing(db, args):
    result = preview(
        db, args.subject, args.evidence, args.corpus, args.cursor, mechanism=args.mechanism
    )
    print(json.dumps(result, indent=2))


def begin(db, args):
    result = start_related(
        db,
        attempt_id=args.attempt,
        subject=args.subject,
        evidence_id=args.evidence,
        corpus_version=args.corpus,
        reference=args.reference,
        mechanism=args.mechanism,
    )
    result.pop("source_key", None)
    print(json.dumps(result, indent=2))


def commands():
    return {"related-pins": listing, "start-related-pin": begin}
