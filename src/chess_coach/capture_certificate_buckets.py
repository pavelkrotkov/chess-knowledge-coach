"""Address bounded certificates by owner and evidence without scanning directories."""

from functools import partial

from .capture_certificate_paths import paths, watch
from .capture_certificate_store import LIMIT, _valid, binding, load
from .opening_study_source import fingerprint
from .short_mate_trend_store import read, write


def _in_bucket(key, index):
    return str(int(key)) == key and int(key) > 0 and (int(key) - 1) // LIMIT == index


def _valid_bucket(data, expected, *, index):
    return _valid(data, expected) and all(_in_bucket(key, index) for key in data["certificates"])


def _load(db, subject, path, evidence_id):
    index = (evidence_id - 1) // LIMIT
    return read(path, binding(db, subject), validator=partial(_valid_bucket, index=index))


def observe(db, root, subject, evidence_id):
    selected = paths(db, root, subject, evidence_id)
    before = fingerprint(selected)
    data = _load(db, subject, selected[0], evidence_id)
    # An unreadable existing bucket is not permission to reuse an old certificate.
    if data is None and before[0] is None:
        data = load(db, root, subject)
    entry = data["certificates"].get(str(evidence_id)) if data else None
    return (selected, before, entry) if entry else None


def publish(db, root, subject, evidence_id, certificates):
    selected = paths(db, root, subject, evidence_id)
    path = selected[0]
    path.parent.mkdir(mode=0o700, exist_ok=True)
    watch(db, root, subject)
    data = {"binding": binding(db, subject), "certificates": certificates}
    if not _valid_bucket(data, data["binding"], index=(evidence_id - 1) // LIMIT):
        raise ValueError("capture certificates unavailable")
    write(path, data)
