"""Bind a verified public opening line to its selection and source."""

from .fact_fingerprint import canonical, digest
from .opening_reference_source import SOURCE_ARCHIVE


def binding(report, color, item):
    line, data = item["line"], item["profile"]
    snapshot = {
        "prompt_fen": line["fen"],
        "learner_color": color,
        "lines": [" ".join(line["moves"])],
    }
    provenance = {
        "kind": "public",
        "selection_hash": digest(canonical(report)),
        "reference": line["reference"],
        "record": line["record"],
        "source_url": line["site"] or SOURCE_ARCHIVE,
        "archive_sha256": data["source_sha256"],
        "license": data["license"],
        "license_url": data["license_url"],
        "catalog_source": report["catalog_source"],
    }
    return snapshot, provenance
