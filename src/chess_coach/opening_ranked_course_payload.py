"""Build the bounded semantic content of one ranked opening course."""

from .fact_fingerprint import canonical, digest
from .opening_context_preview import preview as public_preview
from .opening_ranked_narrative import ranked as ranked_note
from .opening_recommendation_text import annotate

VERSION = "unfamiliar-opening-course-v4"


def _alternative(item):
    source, fork = item["source"], item["public_fork"]
    provenance = None
    if source is not None:
        profile = source["profile"]
        provenance = {
            "line": source["line"],
            "history": source["source_history"],
            "attribution": {
                key: profile[key] for key in ("source", "source_sha256", "license", "license_url")
            },
        }
    return {
        **{
            key: item[key]
            for key in ("selection", "name", "eco", "san", "uci", "history", "history_incomplete")
        },
        "source": provenance,
        "comparison": item["comparison"],
        "public_fork": {
            "status": fork["status"],
            "binding_sha256": fork.get("binding_sha256"),
            "coverage_status": fork.get("coverage", {}).get("status"),
        },
    }


def build_from_context(context):
    """Build from an already-qualified observation; the caller rechecks its guard."""
    report, item, parent = context["report"], context["item"], context["parent"]
    chosen = public_preview(report, context["choice"])
    if chosen["item"] != item:
        raise ValueError("opening selection changed")
    explanation = ranked_note(context)
    chapter = annotate(chosen["chapter"], explanation)
    scope = {
        key: report[key]
        for key in (
            "catalog",
            "reference_index_sha256",
            "sample",
            "sample_identity",
            "sample_failed",
            "sample_incomplete",
            "coverage",
            "limits",
        )
    }
    parent_scope = {
        key: parent[key]
        for key in (
            "parent",
            "path",
            "occurrences",
            "catalog_screened",
            "catalog_screen_limit",
            "omitted_screened",
            "screen_incomplete",
            "truncated",
            "fit",
            "development",
        )
    }
    parent_scope["items"] = [_alternative(other) for other in parent["items"]]
    profile = {key: value for key, value in item["source"]["profile"].items() if key != "examples"}
    payload = {
        "schema": VERSION,
        "choice": context["choice"],
        "selection": item["selection"],
        "admission": context["admission"],
        "context": chosen["context"],
        "name": item["name"],
        "eco": item["eco"],
        "san": item["san"],
        "parent": parent_scope,
        "distance": item["distance"],
        "profile": profile,
        "scope": scope,
        "explanation": explanation,
        "chapters": [chapter],
    }
    return {**payload, "version": digest(canonical(payload))}
