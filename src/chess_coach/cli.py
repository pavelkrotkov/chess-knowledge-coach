"""Command-line entry point."""

import json

from . import cli_commands_datasets as datasets
from . import cli_commands_games as games
from . import cli_commands_learning as learning
from . import cli_curriculum as curriculum
from . import cli_deep_execution as deep_execution
from . import cli_deep_selection as deep_selection
from . import cli_pipeline, cli_recurrence
from . import cli_public_training as public_training
from . import cli_recovery as recovery
from . import cli_related_capture as related_capture
from . import cli_related_fork as related_fork
from . import cli_snapshot as snapshot
from . import cli_unified_practice as unified_practice
from .capabilities import capability_report
from .cli_parser import build_parser
from .competency_coverage import competency_report
from .competency_graph import seed_competency_graph
from .db import Database

COMMANDS = {
    "related-forks": related_fork.listing,
    "start-related-fork": related_fork.begin,
    "related-captures": related_capture.listing,
    "start-related-capture": related_capture.begin,
    "list-own-game-practice": unified_practice.handle_list,
    "list-pawn-practice": unified_practice.handle_list_pawn,
    "start-unified": unified_practice.handle_start,
    "show-unified": unified_practice.handle_show,
    "move-unified": unified_practice.handle_move,
    "hint-unified": unified_practice.handle_hint,
    "import-public-training": public_training.handle_import,
    "list-public-training": public_training.handle_list,
    "show-public-training": public_training.handle_show,
    "run-deep": deep_execution.handle_run,
    "select-deep": deep_selection.handle_select,
    "show-deep-selection": deep_selection.handle_show,
    "list-deep-selections": deep_selection.handle_list,
    "process-pipeline": cli_pipeline.handle_process_pipeline,
    "pipeline-status": cli_pipeline.handle_pipeline_status,
    "init-db": games.handle_init_db,
    "ingest-pgn": games.handle_ingest_pgn,
    "analyze-game": games.handle_analyze_game,
    "inspect-decision": games.handle_inspect_decision,
    "inspect-mate": games.handle_inspect_mate,
    "inspect-pawn": games.handle_inspect_pawn,
    "predict-maia": games.handle_predict_maia,
    "sync-lichess": games.handle_sync_lichess,
    "import-openings": datasets.handle_import_openings,
    "import-lichess-openings": datasets.handle_import_lichess_openings,
    "repertoire": datasets.handle_repertoire,
    "classify-opening": datasets.handle_classify_opening,
    "extract-structures": datasets.handle_extract_structures,
    "structure-history": datasets.handle_structure_history,
    "record-motifs": datasets.handle_record_motifs,
    "import-puzzles": datasets.handle_import_puzzles,
    "stage-puzzles": datasets.handle_stage_puzzles,
    "corpus-status": datasets.handle_corpus_status,
    "query-puzzles": datasets.handle_query_puzzles,
    "style-choices": learning.handle_style_choices,
    "recurrence": cli_recurrence.handle,
    "validate-evidence": learning.handle_validate_evidence,
    "list-evidence": learning.handle_list_evidence,
    "inspect-evidence": learning.handle_inspect_evidence,
    "review-evidence": learning.handle_review_evidence,
    "update-mastery": learning.handle_update_mastery,
    "mastery-report": learning.handle_mastery_report,
    "create-training": learning.handle_create_training,
    "create-puzzle-training": learning.handle_create_puzzle_training,
    "due-training": learning.handle_due_training,
    "review-training": learning.handle_review_training,
    "evidence-report": learning.handle_evidence_report,
    "daily-plan": curriculum.handle_daily_plan,
    "start-puzzle": learning.handle_start_puzzle,
    "show-puzzle": learning.handle_show_puzzle,
    "play-puzzle": learning.handle_play_puzzle,
    "hint-puzzle": learning.handle_hint_puzzle,
}


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "capabilities":
        print(json.dumps(capability_report(), indent=2))
        return
    if args.command == "competencies":
        print(json.dumps(competency_report(), indent=2))
        return
    if args.command == "seed-competencies":
        db = Database(args.db)
        db.initialize()
        print(json.dumps({"skills": seed_competency_graph(db)}))
        return
    if args.command in recovery.COMMANDS:
        recovery.COMMANDS[args.command](args)
        return
    if args.command in snapshot.COMMANDS:
        snapshot.COMMANDS[args.command](args)
        return
    db = Database(args.db)
    db.initialize()
    COMMANDS[args.command](db, args)


if __name__ == "__main__":
    main()
