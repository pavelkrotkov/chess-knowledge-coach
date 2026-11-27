"""Build a ranked teaching course from two independently replayed public records."""

from .course_pgn import chapter
from .fact_fingerprint import canonical, digest
from .opening_context_preview import preview as public_preview
from .opening_ranked_course_payload import build_from_context

VERSION = "unfamiliar-opening-course-v5"


def _practice(course, second):
    line, history = second["line"], second["history"]
    profile, selection = course["profile"], course["selection"]
    source = {
        "kind": "public",
        "reference": line["reference"],
        "record": line["record"],
        "san": line["san"],
        "source_url": line["site"] or profile["source"],
        "license": profile["license"],
        "license_url": profile["license_url"],
        "source_sha256": profile["source_sha256"],
        "index_sha256": course["scope"]["reference_index_sha256"],
        "history": history,
    }
    snapshot = {
        "prompt_fen": line["fen"],
        "learner_color": selection["color"],
        "lines": [" ".join(line["moves"])],
    }
    color = selection["color"].capitalize()
    attribution = "Public source: {source_url}; {license}: {license_url}.".format(**source)
    note = (
        f"Play {color}. Pause before revealing the recorded line. "
        "This public rehearsal is ungraded; other legal moves are not assessed. "
        "Owners and editors may see answers. Study play does not update local practice. "
        + attribution
    )
    return {
        **chapter("Practice: recorded rehearsal", note, snapshot, source, guidance=note),
        "kind": "practice",
    }


def assemble(context, qualification):
    """Build deterministic teaching roles from qualified, source-bound records."""
    original = build_from_context(context)
    second = qualification["second"]
    example = public_preview(context["report"], context["choice"])["chapter"]
    snapshot = example["source_snapshot"]
    short = {**snapshot, "lines": [snapshot["lines"][0].split()[0]]}
    explanation = chapter(
        "Explanation: why study this opening",
        original["explanation"],
        short,
        example["source"],
        guidance=original["explanation"],
    )
    first_record = context["item"]["source"]["line"]["record"]
    example = {
        **example,
        "kind": "example",
        "source": {**example["source"], "record": first_record},
    }
    chapters = [{**explanation, "kind": "explanation"}, example]
    if second:
        chapters.append(_practice(original, second))
    payload = {
        **{key: value for key, value in original.items() if key != "version"},
        "schema": VERSION,
        "source_version": original["version"],
        "public_status": "available" if second else "incomplete",
        "rehearsal_coverage": {key: qualification[key] for key in ("checked", "limit", "more")},
        "chapters": chapters,
    }
    return {**payload, "version": digest(canonical(payload))}
