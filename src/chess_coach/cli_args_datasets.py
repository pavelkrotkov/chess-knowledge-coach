"""Arguments for datasets commands."""

from pathlib import Path

from .named_structures import VERSION, VERSIONS


def configure(sub):
    openings = sub.add_parser("import-openings")
    openings.add_argument("path", type=Path)
    openings.add_argument("--version", required=True)
    openings.add_argument("--source-url", required=True)
    sub.add_parser("import-lichess-openings", help="Import the pinned CC0 opening snapshot")
    report = sub.add_parser("repertoire", help="Report attributable opening history")
    report.add_argument("--learner", required=True)
    classify = sub.add_parser("classify-opening")
    classify.add_argument("game_id", type=int)
    classify.add_argument("--version", required=True)
    classify.add_argument("--source-url", required=True)
    structures = sub.add_parser("extract-structures")
    structures.add_argument("game_id", type=int)
    structures.add_argument("--detector-version", default="0.1.0")
    history = sub.add_parser(
        "structure-history", help="Report named structures in attributable games"
    )
    history.add_argument("--learner", required=True)
    history.add_argument("--matcher-version", choices=VERSIONS, default=VERSION)
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
    stage = sub.add_parser("stage-puzzles", help="Import a decoded project-local corpus")
    stage.add_argument("path", type=Path)
    stage.add_argument("--project-root", required=True, type=Path)
    stage.add_argument("--version", required=True)
    stage.add_argument("--csv-sha256", required=True)
    stage.add_argument("--archive-sha256")
    stage.add_argument("--selection-manifest", type=Path)
    stage.add_argument("--source-url")
    stage.add_argument("--max-rows", type=int, default=1000)
    stage.add_argument("--batch-size", type=int, default=100)
    stage.add_argument("--enable-wal", action="store_true")
    stage.add_argument("--min-free-bytes", type=int, default=10 * 1024**3)
    sub.add_parser("corpus-status", help="Report corpus and import progress")
    puzzle_query = sub.add_parser("query-puzzles")
    puzzle_query.add_argument("--version", required=True)
    puzzle_query.add_argument("--theme")
    puzzle_query.add_argument("--operation")
    puzzle_query.add_argument("--min-rating", type=int)
    puzzle_query.add_argument("--max-rating", type=int)
    puzzle_query.add_argument("--limit", type=int, default=100)
    puzzle_query.add_argument("--offset", type=int, default=0)
    puzzle_query.add_argument("--after-rating", type=int)
    puzzle_query.add_argument("--after-id")
