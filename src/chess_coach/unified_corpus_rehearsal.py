"""Identify supported corpus supplied-line rehearsals."""

import json


def direct_corpus(row):
    return (
        row["source_type"] == "corpus"
        and row["objective"] == "legal_line"
        and set(json.loads(row["provenance_json"])) == {"corpus_checksum"}
    )


def supplied_corpus(row):
    if direct_corpus(row):
        return True
    if row["source_type"] != "corpus" or row["objective"] != "legal_line":
        return False
    data = json.loads(row["provenance_json"])
    related = {
        "related_capture",
        "related_fork",
        "related_protection",
        "related_mate",
        "related_created_exposure",
        "related_fork_prevention",
        "related_fork_avoidance",
        "related_pin",
        "related_backrank_attack",
        "related_backrank_defense",
    }
    keys = set(data) - {"corpus_checksum"}
    if "corpus_checksum" not in data or len(keys) != 1 or not keys <= related:
        return False
    binding = data[next(iter(keys))]
    return isinstance(binding, dict) and "assessment" not in binding
