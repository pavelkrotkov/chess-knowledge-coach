"""Apply only a certified unfamiliar fork objective to a filtered snapshot."""


def apply(snapshot, provenance, provenance_key):
    if provenance_key == "related_fork" and provenance and provenance.get("assessment"):
        from .related_fork_assessment_current import apply as apply_assessment

        apply_assessment(snapshot, provenance["assessment"])
