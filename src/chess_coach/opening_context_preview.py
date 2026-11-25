"""Revalidate one exact exploratory context and build its private preview."""

from .course_pgn import chapter
from .fact_fingerprint import canonical, digest
from .opening_context_choice import select
from .opening_context_display import _path


def preview(report, value):
    item = select(report, value)
    source, selection = item["source"], item["selection"]
    line, profile = source["line"], source["profile"]
    snapshot = {
        "prompt_fen": line["fen"],
        "learner_color": selection["color"],
        "lines": [" ".join(line["moves"])],
    }
    provenance = {
        "kind": "public",
        "selection": value,
        "reference": line["reference"],
        "source_url": line["site"] or profile["source"],
        "license": profile["license"],
        "license_url": profile["license_url"],
        "index_sha256": report["reference_index_sha256"],
        "history": source["source_history"],
    }
    note = (
        f"Observed public continuation from {provenance['source_url']}. "
        f"Source: Lichess broadcasts, {profile['source']}; "
        f"license: {profile['license']}, {profile['license_url']}. "
        "History outside the checked sample is unknown."
    )
    result = chapter(item["name"], note, snapshot, provenance)
    payload = {"schema": "opening-context-course-v1", "selection": selection, "chapter": result}
    return {
        "version": digest(canonical(payload)),
        "selection": selection,
        "context": _path(selection["path"]),
        "chapter": result,
        "item": item,
    }
