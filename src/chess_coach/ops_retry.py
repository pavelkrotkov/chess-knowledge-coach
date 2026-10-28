"""Retry only due server backoffs without repeating analysis."""

import os

from .db import Database
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
        if result is not None and result.get("status") == "failed":
            raise SystemExit("cooldown retry synchronization failed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
