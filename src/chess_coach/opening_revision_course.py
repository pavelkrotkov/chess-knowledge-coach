"""Build a deterministic, source-bound private opening course preview."""

from .fact_fingerprint import canonical, digest
from .opening_course_chapters import owned, public
from .opening_course_public import continuation
from .opening_experiment_current import current

VERSION = "opening-revision-course-v1"


def preview(db, root, learner, game_id, position_id, move):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    decision, choice, experiment, identity = current(
        db, root, learner, game_id, position_id, move, with_identity=True
    )
    example, status = continuation(
        root, learner, decision["catalog"]["parent"], move, experiment["alternative"]["uci"].split()
    )
    chapters = [owned(decision, choice, experiment)]
    if example is not None:
        chapters.append(public(example))
    payload = {
        "version": VERSION,
        "source": identity,
        "chapters": chapters,
        "public_status": status,
    }
    version = digest(canonical(payload))
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("opening course changed")
    return {
        "version": version,
        "schema": VERSION,
        "chapters": chapters,
        "public_status": status,
        "decision": decision,
        "choice": choice,
        "experiment": experiment,
    }
