"""Handlers for datasets commands."""

import json

from .motifs import record_motif_opportunities
from .named_structure_report import structure_report
from .opening_snapshot import import_snapshot
from .openings import classify_game, import_openings
from .puzzle_import import stage_puzzles
from .puzzle_import_report import corpus_report
from .puzzles import import_puzzles, query_puzzles
from .repertoire import repertoire_report
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
                after_rating=args.after_rating,
                after_id=args.after_id,
            ),
            indent=2,
        )
    )


def handle_stage_puzzles(db, args):
    result = stage_puzzles(
        db,
        args.path,
        project_root=args.project_root,
        version=args.version,
        csv_sha256=args.csv_sha256,
        archive_sha256=args.archive_sha256,
        source_url=args.source_url,
        max_rows=args.max_rows,
        batch_size=args.batch_size,
        enable_wal=args.enable_wal,
        min_free_bytes=args.min_free_bytes,
        selection_manifest=args.selection_manifest,
    )
    print(json.dumps(result, indent=2))


def handle_corpus_status(db, args):
    print(json.dumps(corpus_report(db), indent=2))


def handle_structure_history(db, args):
    print(json.dumps(structure_report(db, args.learner, version=args.matcher_version), indent=2))


def handle_import_lichess_openings(db, args):
    print(json.dumps({"rows": import_snapshot(db)}, indent=2))


def handle_repertoire(db, args):
    print(json.dumps(repertoire_report(db, args.learner), indent=2))
