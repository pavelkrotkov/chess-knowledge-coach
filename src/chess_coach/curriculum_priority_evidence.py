"""Read bounded current reviewed contexts once per supported family."""

from .mastery_eligibility import eligible_contexts
from .mastery_policy import calculate


def family(db, learner, skill, now, limit, check):
    rows = db.connection.execute(
        """SELECT id FROM evidence_mappings INDEXED BY idx_curriculum_evidence
        WHERE subject=? AND skill=? AND operation='execute' ORDER BY id LIMIT ?""",
        (learner, skill, limit + 1),
    ).fetchall()
    check()
    if len(rows) > limit:
        return {"state": "incomplete", "contexts": None, "mastery": None, "uncertainty": None}
    contexts, _ = eligible_contexts(db, learner, skill, "execute", now)
    check()
    values = calculate(contexts)
    return {
        "state": values["status"],
        "contexts": values["context_count"],
        "mastery": values["mastery"],
        "uncertainty": values["uncertainty"],
    }
