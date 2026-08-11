from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .db import Database
from .evidence import evidence_report, validate_evidence
from .ingest import ingest_pgn
from .lichess import LichessClient
from .mastery import mastery_report, update_mastery
from .motifs import record_motif_opportunities
from .openings import classify_game, import_openings
from .puzzles import import_puzzles, query_puzzles
from .structures import extract_game_episodes
from .training import create_training_item, due_items, review_item


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-first chess knowledge coach")
    parser.add_argument("--db", default="coach.sqlite", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    ingest = sub.add_parser("ingest-pgn")
    ingest.add_argument("path", type=Path)
    sync = sub.add_parser("sync-lichess", help="Import a user's Lichess game export")
    sync.add_argument("username")
    sync.add_argument("--max-games", type=int, default=100)
    sync.add_argument("--page-size", type=int, default=100)
    sync.add_argument("--since", type=int)
    openings = sub.add_parser("import-openings")
    openings.add_argument("path", type=Path)
    openings.add_argument("--version", required=True)
    openings.add_argument("--source-url", required=True)
    classify = sub.add_parser("classify-opening")
    classify.add_argument("game_id", type=int)
    classify.add_argument("--version", required=True)
    classify.add_argument("--source-url", required=True)
    structures = sub.add_parser("extract-structures")
    structures.add_argument("game_id", type=int)
    structures.add_argument("--detector-version", default="0.1.0")
    motifs = sub.add_parser("record-motifs")
    motifs.add_argument("position_id", type=int)
    motifs.add_argument("--detector-version", default="0.1.0")
    motifs.add_argument("--mapper-version", default="0.1.0")
    motifs.add_argument("--operation", default="prevent")
    motifs.add_argument(
        "--outcome", choices=["success", "failure", "ambiguous"], default="ambiguous"
    )
    puzzle_import = sub.add_parser("import-puzzles")
    puzzle_import.add_argument("path", type=Path)
    puzzle_import.add_argument("--version", required=True)
    puzzle_query = sub.add_parser("query-puzzles")
    puzzle_query.add_argument("--version", required=True)
    puzzle_query.add_argument("--theme")
    puzzle_query.add_argument("--operation")
    puzzle_query.add_argument("--min-rating", type=int)
    puzzle_query.add_argument("--max-rating", type=int)
    puzzle_query.add_argument("--limit", type=int, default=100)
    puzzle_query.add_argument("--offset", type=int, default=0)
    validate = sub.add_parser("validate-evidence")
    validate.add_argument("evidence_id", type=int)
    mastery_update = sub.add_parser("update-mastery")
    mastery_update.add_argument("skill")
    mastery_update.add_argument("operation")
    sub.add_parser("mastery-report")
    training_create = sub.add_parser("create-training")
    training_create.add_argument("source_type", choices=["game", "puzzle", "canonical"])
    training_create.add_argument("source_ref")
    training_create.add_argument("skill")
    training_create.add_argument("operation")
    training_due = sub.add_parser("due-training")
    training_due.add_argument("--limit", type=int, default=100)
    training_review = sub.add_parser("review-training")
    training_review.add_argument("item_id", type=int)
    training_review.add_argument("rating", choices=["again", "hard", "good", "easy"])
    training_review.add_argument("--elapsed-seconds", type=int)
    sub.add_parser("evidence-report")
    args = parser.parse_args()
    db = Database(args.db)
    db.initialize()
    if args.command == "init-db":
        print(f"initialized {args.db}")
    elif args.command == "ingest-pgn":
        print(json.dumps(ingest_pgn(db, args.path.open()), indent=2))
    elif args.command == "sync-lichess":
        client = LichessClient(token=os.environ.get("LICHESS_API_TOKEN"))
        print(
            json.dumps(
                client.sync_user(
                    db,
                    args.username,
                    max_games=args.max_games,
                    page_size=args.page_size,
                    since=args.since,
                ),
                indent=2,
            )
        )
    elif args.command == "import-openings":
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
    elif args.command == "classify-opening":
        print(
            json.dumps(
                classify_game(db, args.game_id, version=args.version, source_url=args.source_url),
                indent=2,
            )
        )
    elif args.command == "extract-structures":
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
    elif args.command == "record-motifs":
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
    elif args.command == "import-puzzles":
        print(json.dumps({"rows": import_puzzles(db, args.path, version=args.version)}, indent=2))
    elif args.command == "query-puzzles":
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
    elif args.command == "validate-evidence":
        validate_evidence(db, args.evidence_id)
        print(json.dumps({"validated": args.evidence_id}, indent=2))
    elif args.command == "update-mastery":
        print(json.dumps(update_mastery(db, skill=args.skill, operation=args.operation), indent=2))
    elif args.command == "mastery-report":
        print(json.dumps(mastery_report(db), indent=2))
    elif args.command == "create-training":
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
    elif args.command == "due-training":
        print(json.dumps(due_items(db, limit=args.limit), indent=2, default=str))
    elif args.command == "review-training":
        print(
            json.dumps(
                review_item(db, args.item_id, args.rating, elapsed_seconds=args.elapsed_seconds),
                indent=2,
            )
        )
    elif args.command == "evidence-report":
        print(json.dumps(evidence_report(db), indent=2))


if __name__ == "__main__":
    main()
