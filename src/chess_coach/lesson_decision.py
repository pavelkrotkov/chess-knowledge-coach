"""Find current learner-owned coaching sources for a single decision."""

from .learner_identity import normalize_identity
from .lesson_cues import CUES
from .lesson_mechanisms import describe
from .lesson_narrative import qualification
from .lesson_possible import MECHANISMS
from .lesson_source import source


def lessons(db, learner, position_id):
    rows = db.connection.execute(
        """SELECT e.id, e.position_id FROM evidence_mappings e
        WHERE e.position_id=? AND e.subject=? ORDER BY e.id DESC LIMIT 30""",
        (position_id, normalize_identity(learner)),
    ).fetchall()
    result = []
    for row in rows:
        inspected = source(db, learner, row)
        if not inspected:
            continue
        family = inspected["evidence"]["mapping_producer"]
        item = describe(inspected)
        if item and family in CUES:
            question, habit, practice = CUES[family]
            item["context"] = {}
            result.append(
                {
                    "examples": [item],
                    "family": family,
                    "possible": MECHANISMS[family],
                    "question": question,
                    "habit": habit,
                    "practice": practice,
                    "qualification": qualification(family),
                }
            )
    return result
