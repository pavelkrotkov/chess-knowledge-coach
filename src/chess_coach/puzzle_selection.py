"""Validate the narrowly supported source-order prefix provenance."""

import json
import re

FIELDS = frozenset(
    {
        "policy",
        "fullsource_count",
        "selected_count",
        "parent_csv_sha256",
        "parent_archive_sha256",
        "derived_csv_sha256",
        "representative",
    }
)


def validate_selection(value: object, csv_sha256: str, archive_sha256: str | None) -> str:
    """Return canonical JSON after checking the declared selection and identities."""
    if not isinstance(value, dict) or value.keys() != FIELDS:
        raise ValueError("invalid selection manifest fields")
    if value["policy"] != "source_order_prefix" or value["representative"] is not False:
        raise ValueError("unsupported selection policy")
    _counts(value["fullsource_count"], value["selected_count"])
    _digests(value)
    if (
        value["derived_csv_sha256"] != csv_sha256
        or value["parent_archive_sha256"] != archive_sha256
    ):
        raise ValueError("selection does not match import source identity")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _counts(full: object, selected: object) -> None:
    if type(full) is not int or type(selected) is not int:
        raise ValueError("invalid selection counts")
    if not 1 <= selected <= full <= 2**63 - 1:
        raise ValueError("invalid selection counts")


def _digests(value: dict) -> None:
    for field in ("parent_csv_sha256", "parent_archive_sha256", "derived_csv_sha256"):
        if not isinstance(value[field], str) or not re.fullmatch(r"[0-9a-f]{64}", value[field]):
            raise ValueError("invalid selection digest")
