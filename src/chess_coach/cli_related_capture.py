"""Command-line previews and source-bound capture transfer sessions."""

import json

from .related_capture import preview
from .related_capture_start import start_related


def configure(sub):
    listing = sub.add_parser("related-captures")
    listing.add_argument("--subject", required=True)
    listing.add_argument("--position", required=True, type=int)
    listing.add_argument("--corpus", required=True)
    listing.add_argument("--cursor")
    begin = sub.add_parser("start-related-capture")
    begin.add_argument("--subject", required=True)
    begin.add_argument("--position", required=True, type=int)
    begin.add_argument("--corpus", required=True)
    begin.add_argument("--attempt", required=True)
    begin.add_argument("--reference", required=True)


def listing(db, args):
    print(json.dumps(preview(db, args.subject, args.position, args.corpus, args.cursor), indent=2))


def begin(db, args):
    result = start_related(
        db,
        attempt_id=args.attempt,
        subject=args.subject,
        position=args.position,
        corpus_version=args.corpus,
        reference=args.reference,
    )
    result.pop("source_key", None)
    print(json.dumps(result, indent=2))
