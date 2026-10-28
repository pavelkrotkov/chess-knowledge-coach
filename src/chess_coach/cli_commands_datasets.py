"""Handlers for datasets commands."""

import json

from .motifs import record_motif_opportunities
from .openings import classify_game, import_openings
from .puzzles import import_puzzles, query_puzzles
from .structures import extract_game_episodes


def handle_import_openings(db, args):
    print(
        json.dumps(
            {
                "rows": import_openings(
                    db, args.path, version=args.version, source_url=args.source_url
                )
            },
            indent=2,
        )
    )


def handle_classify_opening(db, args):
    print(
        json.dumps(
            classify_game(db, args.game_id, version=args.version, source_url=args.source_url),
            indent=2,
        )
    )


def handle_extract_structures(db, args):
    print(
        json.dumps(
            {
                "episodes": extract_game_episodes(
                    db, args.game_id, detector_version=args.detector_version
                )
            },
            indent=2,
        )
    )


def handle_record_motifs(db, args):
    print(
        json.dumps(
            {
                "facts": record_motif_opportunities(
                    db,
                    args.position_id,
                    detector_version=args.detector_version,
                    mapper_version=args.mapper_version,
                    operation=args.operation,
                    outcome=args.outcome,
                )
            },
            indent=2,
        )
    )


def handle_import_puzzles(db, args):
    print(json.dumps({"rows": import_puzzles(db, args.path, version=args.version)}, indent=2))


def handle_query_puzzles(db, args):
    print(
        json.dumps(
            query_puzzles(
                db,
                version=args.version,
                theme=args.theme,
                operation=args.operation,
                min_rating=args.min_rating,
                max_rating=args.max_rating,
                limit=args.limit,
                offset=args.offset,
            ),
            indent=2,
        )
    )
