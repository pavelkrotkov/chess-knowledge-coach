"""Recognize separately bound immediate-mate practice contracts."""

from .related_discovery_contract import is_source as discovery_mate
from .unified_corpus_mate import is_source as corpus_mate


def immediate(row):
    return discovery_mate(row) or (row["next_index"] == 0 and corpus_mate(row))
