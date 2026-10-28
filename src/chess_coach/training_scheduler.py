"""FSRS configuration, timestamp validation, and card reconstruction."""

from datetime import UTC, datetime
from importlib.metadata import version as package_version

from fsrs import Rating, Scheduler

SCHEDULER_VERSION = f"fsrs-{package_version('fsrs')}"
RATINGS = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def scheduler_config(scheduler: Scheduler) -> dict:
    return {
        "parameters": list(scheduler.parameters),
        "desired_retention": scheduler.desired_retention,
        "learning_steps_seconds": [step.total_seconds() for step in scheduler.learning_steps],
        "relearning_steps_seconds": [step.total_seconds() for step in scheduler.relearning_steps],
        "maximum_interval": scheduler.maximum_interval,
        "enable_fuzzing": scheduler.enable_fuzzing,
    }


def duration_ms(elapsed_seconds: int | None) -> int | None:
    if elapsed_seconds is None:
        return None
    if type(elapsed_seconds) is not int or not 0 <= elapsed_seconds <= (2**63 - 1) // 1000:
        raise ValueError("elapsed_seconds must be a non-negative integer within supported range")
    return elapsed_seconds * 1000
