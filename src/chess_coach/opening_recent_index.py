"""Build a separate CC0 rated-game index from one verified prefix."""

from functools import partial
from pathlib import Path

from .opening_profile_store import store
from .opening_recent_capacity import check as capacity
from .opening_recent_context import record
from .opening_recent_coverage import context_coverage
from .opening_recent_read import text
from .opening_recent_source import (
    INDEX_NAME,
    KIND,
    LICENSE,
    LICENSE_URL,
    MONTH,
    SOURCE,
    TRANSFORM,
    URL,
)
from .opening_reference_games import collect
from .opening_reference_publish import publish
from .tactical_study_path import planning


def metadata(receipt):
    return {
        "source_kind": KIND,
        "source_sha256": receipt["prefix_sha256"],
        "source_url": SOURCE,
        "source_archive": URL,
        "source_month": MONTH,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "retrieved_at": receipt["retrieved_at"],
        "range_start": 0,
        "range_end": receipt["range_end"],
        "prefix_bytes": receipt["prefix_bytes"],
        "etag": receipt["etag"],
        "last_modified": receipt["last_modified"],
        "filters": "standard legal completed rated-source games; context selection before sample cap",
        "archive_bytes": receipt["archive_bytes"],
        "whole_archive_checksum_verified": False,
    }


def build(root, subject):
    root = Path(root).resolve(strict=True)
    directory, _ = planning(root, subject)
    capacity(root, directory)
    contents, receipt = text(directory)
    records, coverage = collect(contents, True, parser=record)
    coverage.update(context_coverage(records))
    capacity(root, directory)
    return publish(
        directory,
        INDEX_NAME,
        records,
        coverage,
        partial(store, transform=TRANSFORM, source_metadata=metadata(receipt)),
    )
