"""Retry due server backoffs and process bounded local verifications."""

import os

from .db import Database
from .objective_worker import process as process_objectives
from .ops_worker import database_path
from .pipeline_config import PipelineConfig
from .pipeline_sync import sync_result


def main() -> None:
    learner = os.environ.get("LICHESS_USERNAME")
    if not learner:
        raise SystemExit("LICHESS_USERNAME is required")
    db = Database(database_path())
    try:
        result = sync_result(
            db,
            PipelineConfig(learner=learner),
            os.environ.get("LICHESS_API_TOKEN"),
            None,
            None,
            retry_only=True,
        )
        process_objectives(db, learner)
        if result is not None and result.get("status") == "failed":
            raise SystemExit("cooldown retry synchronization failed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
