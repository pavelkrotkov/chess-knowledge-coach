"""Handlers for games commands."""

import json
import os

from .analysis import analyze_game
from .decision_inspection import inspect_decision
from .enrichment import SubprocessMaiaAdapter, UnavailableMaiaAdapter, predict_maia
from .ingest import ingest_pgn
from .lichess import LichessClient
from .mate_inspection import inspect_mate
from .pawn_inspection import inspect_pawn


def handle_init_db(db, args):
    print(f"initialized {args.db}")


def handle_ingest_pgn(db, args):
    print(json.dumps(ingest_pgn(db, args.path.open()), indent=2))


def handle_analyze_game(db, args):
    print(
        json.dumps(
            {
                "analysis_run_id": analyze_game(
                    db,
                    args.game_id,
                    engine_path=args.engine_path,
                    nodes=args.nodes,
                    depth=args.depth,
                    multipv=args.multipv,
                    threads=args.threads,
                    hash_mb=args.hash_mb,
                )
            },
            indent=2,
        )
    )


def handle_inspect_decision(db, args):
    print(
        json.dumps(
            inspect_decision(
                db, args.position_id, run_id=args.run_id, learner=os.environ.get("LICHESS_USERNAME")
            ),
            indent=2,
        )
    )


def handle_inspect_mate(db, args):
    print(
        json.dumps(
            inspect_mate(
                db,
                args.position_id,
                learner=os.environ.get("LICHESS_USERNAME"),
                expected_fingerprint=args.source_fingerprint,
            ),
            indent=2,
        )
    )


def handle_inspect_pawn(db, args):
    print(
        json.dumps(
            inspect_pawn(
                db,
                args.position_id,
                learner=os.environ.get("LICHESS_USERNAME"),
                expected_fingerprint=args.source_fingerprint,
            ),
            indent=2,
        )
    )


def handle_predict_maia(db, args):
    adapter = (
        SubprocessMaiaAdapter(
            executable=args.maia_command, model=args.model, checkpoint=args.checkpoint
        )
        if args.maia_command
        else UnavailableMaiaAdapter()
    )
    print(json.dumps(predict_maia(db, args.position_id, adapter), indent=2))


def handle_sync_lichess(db, args):
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
