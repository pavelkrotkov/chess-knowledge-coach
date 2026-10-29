"""Pause imports before exhausting project-local storage."""

import shutil
from pathlib import Path


class ImportBudgetError(ValueError):
    """The configured storage reserve would be breached."""


def validate_reserve(minimum: int) -> None:
    if minimum < 0:
        raise ValueError("storage reserve cannot be negative")


def check_reserve(directory: Path, minimum: int) -> None:
    validate_reserve(minimum)
    if shutil.disk_usage(directory).free < minimum:
        raise ImportBudgetError("project storage reserve reached")
