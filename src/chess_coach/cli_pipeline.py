"""CLI adapter for the bounded processing entry point."""

import json
import os

from .pipeline import process_pipeline
from .pipeline_config import PipelineConfig
from .pipeline_status import pipeline_status


def handle_process_pipeline(db, args):
    names = (
        "max_games",
        "max_scan",
        "max_positions",
        "nodes",
        "seconds_per_position",
        "threads",
        "hash_mb",
        "engine_path",
        "page_size",
        "network_retries",
        "network_requests",
        "network_timeout",
        "network_seconds",
        "network_bytes",
        "network_sleep",
        "opening_version",
        "opening_source",
        "structure_version",
        "classifier_version",
        "ontology_version",
        "tactical_version",
        "deep_enabled",
        "deep_max_scan",
        "deep_max_games",
        "deep_per_game",
        "deep_max_jobs",
        "deep_nodes",
        "deep_seconds",
        "deep_multipv",
        "mate_enabled",
        "mate_max_scan",
        "mate_max_decisions",
        "material_enabled",
        "material_max_scan",
        "material_max_decisions",
    )
    learner = args.username or os.environ.get("LICHESS_USERNAME")
    if not learner:
        raise SystemExit("learner is required as an argument or LICHESS_USERNAME")
    config = PipelineConfig(learner=learner, **{name: getattr(args, name) for name in names})
    result = process_pipeline(db, config, token=os.environ.get("LICHESS_API_TOKEN"))
    print(json.dumps(result, indent=2))
    if result.get("status") == "failed":
        raise SystemExit(1)


def handle_pipeline_status(db, args):
    print(json.dumps(pipeline_status(db, os.environ.get("LICHESS_USERNAME")), indent=2))
