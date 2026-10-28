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
    )
    learner = args.username or os.environ.get("LICHESS_USERNAME")
    if not learner:
        raise SystemExit("learner is required as an argument or LICHESS_USERNAME")
    config = PipelineConfig(learner=learner, **{name: getattr(args, name) for name in names})
    print(
        json.dumps(
            process_pipeline(db, config, token=os.environ.get("LICHESS_API_TOKEN")), indent=2
        )
    )


def handle_pipeline_status(db, args):
    print(json.dumps(pipeline_status(db), indent=2))
