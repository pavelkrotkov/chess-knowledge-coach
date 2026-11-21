"""Record the tactical positions actually served or possibly published."""

from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .mastery_time import parse_utc
from .tactical_exposure_material import entries
from .tactical_exposure_positions import MAX_TOTAL_POSITIONS


def _prepare(subject, artifact, chapters, line, when):
    identity = normalize_identity(subject)
    if not identity or not isinstance(artifact, str) or len(artifact) != 64:
        raise ValueError("tactical exposure identity unavailable")
    timestamp = datetime.now(UTC) if when is None else parse_utc(when)
    if timestamp is None:
        raise ValueError("tactical exposure time unavailable")
    material = list(entries(chapters, line))
    if sum(len(keys) for _, _, keys in material) > MAX_TOTAL_POSITIONS:
        raise ValueError("tactical material exceeds exposure limit")
    return identity, timestamp.isoformat(), material


def _insert(db, identity, artifact, kind, moment, material):
    for index, chapter_hash, keys in material:
        db.connection.executemany(
            """INSERT OR IGNORE INTO tactical_exposures
            (subject,prompt_key,artifact_hash,chapter_index,chapter_hash,kind,occurred_at)
            VALUES(?,?,?,?,?,?,?)""",
            [(identity, key, artifact, index, chapter_hash, kind, moment) for key in sorted(keys)],
        )


def record(db, subject, artifact, chapters, kind, *, line=None, when=None):
    if db.connection.in_transaction:
        raise RuntimeError("tactical exposure requires an idle connection")
    identity, moment, material = _prepare(subject, artifact, chapters, line, when)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        _insert(db, identity, artifact, kind, moment, material)
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
