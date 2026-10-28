"""Arguments for datasets commands."""

from pathlib import Path


def configure(sub):
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
