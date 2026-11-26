"""Locate the owner-private certificate directory and its bounded files."""

import stat

from .capture_certificate_store import LIMIT, location


def watch(db, root, subject):
    legacy = location(db, root, subject)
    if legacy is None:
        raise ValueError("capture certificate scope unavailable")
    path = legacy.with_name(legacy.name + ".buckets")
    try:
        info = path.lstat()
    except FileNotFoundError:
        return [path, legacy]
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ValueError("capture certificate directory unavailable")
    return [path, legacy]


def paths(db, root, subject, evidence_id):
    if type(evidence_id) is not int or evidence_id < 1:
        raise ValueError("capture evidence unavailable")
    parent, legacy = watch(db, root, subject)
    return [parent / f"{(evidence_id - 1) // LIMIT}.json", legacy]
