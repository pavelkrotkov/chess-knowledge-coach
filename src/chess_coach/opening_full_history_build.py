"""Build a separate immutable index retaining complete admitted public histories."""

import time
from functools import partial
from pathlib import Path

from .opening_full_history_parse import parser
from .opening_profile_store import store
from .opening_recent_capacity import check as capacity
from .opening_recent_coverage import context_coverage
from .opening_recent_index import metadata
from .opening_recent_read import source, text
from .opening_recent_source import TRANSFORM as RECENT_TRANSFORM
from .opening_reference_games import collect
from .opening_reference_publish import publish
from .tactical_study_path import planning

INDEX_NAME = "opening-standard-rated-2026-10-full-history-v1.sqlite"
TRANSFORM = RECENT_TRANSFORM + ";full-validated-history-v1"
SECONDS = 60


def _check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("reference build deadline")


def build(root, subject):
    deadline = time.monotonic() + SECONDS
    root = Path(root).resolve(strict=True)
    directory, _ = planning(root, subject)
    capacity(root, directory, deadline=deadline)
    _check(deadline)
    contents, receipt = text(directory, deadline=deadline)
    rejected = [0]
    check = partial(_check, deadline)
    records, coverage = collect(contents, True, parser=parser(check, rejected), check=check)
    coverage.update(context_coverage(records))
    coverage["over_512_unvalidated"] = rejected[0]
    capacity(root, directory, deadline=deadline)

    def confirm():
        check()
        capacity(root, directory, deadline=deadline)
        check()
        if source(directory)[1] != receipt:
            raise ValueError("recent source changed")
        check()

    return publish(
        directory,
        INDEX_NAME,
        records,
        coverage,
        partial(
            store,
            transform=TRANSFORM,
            source_metadata=metadata(receipt),
            history=True,
            deadline=deadline,
        ),
        confirm=confirm,
    )
