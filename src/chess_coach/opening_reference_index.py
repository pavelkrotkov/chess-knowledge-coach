"""Publish one separate, immutable local index of reference positions."""

from .opening_reference_games import collect
from .opening_reference_publish import publish
from .opening_reference_source import SOURCE_NAME, read
from .opening_reference_store import store as _store
from .tactical_study_path import planning

INDEX_NAME = "opening-reference-broadcast-2026-09-v1.sqlite"


def build(root, subject):
    return _build(root, subject, INDEX_NAME, collect, _store)


def _build(root, subject, index_name, collector, store):
    directory, _ = planning(root, subject)
    output = directory / index_name
    if output.exists() or output.is_symlink():
        raise ValueError("reference index already exists")
    source = directory / SOURCE_NAME
    if source.is_symlink() or source.resolve(strict=True).parent != directory:
        raise ValueError("reference source unavailable")
    text, truncated = read(source)
    records, coverage = collector(text, truncated)
    return publish(directory, index_name, records, coverage, store)
