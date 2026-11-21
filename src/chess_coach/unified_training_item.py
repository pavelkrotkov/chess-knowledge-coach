"""Find or create an owner-bound unified mate scheduler item."""

from .fact_fingerprint import canonical
from .learner_identity import normalize_identity
from .training import create_training_item

SOURCE = "unified_corpus_m1"


def source_ref(subject, version, key, snapshot_hash):
    return canonical([normalize_identity(subject), version, key, snapshot_hash])


def training_item(db, row, item_id, *, source=SOURCE, skill="mate_in_one"):
    ref = source_ref(row["subject"], row["source_version"], row["source_key"], row["snapshot_hash"])
    if item_id is None:
        item_id = create_training_item(
            db, source_type=source, source_ref=ref, skill=skill, operation="execute"
        )
    item = db.connection.execute("SELECT * FROM training_items WHERE id=?", (item_id,)).fetchone()
    if item is None or (
        item["source_type"],
        item["source_ref"],
        item["skill"],
        item["operation"],
    ) != (source, ref, skill, "execute"):
        raise ValueError("training item does not match the qualified source")
    return item_id


def existing(db, row, training, item_id):
    existing = db.connection.execute(
        "SELECT item_id FROM unified_training_enrollments WHERE attempt_id=?", (row["attempt_id"],)
    ).fetchone()
    if existing is None:
        return False
    if not training or (item_id is not None and item_id != existing[0]):
        raise ValueError("attempt belongs to another training request")
    return True
