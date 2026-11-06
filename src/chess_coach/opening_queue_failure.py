"""Persist an unavailable attempt without asserting source currentness."""

import os

from .fact_fingerprint import canonical, digest
from .opening_queue_files import read
from .opening_queue_write import staged, sync

VERSION = "opening-comparison-failure-v1"


def path(directory, item):
    return directory / f"opening-comparison-{item['id']}-{item['attempt']}.failed.json"


def _payload(item):
    return {
        "version": VERSION,
        "request_id": item["id"],
        "attempt": item["attempt"],
        "source_sha256": digest(canonical(item["source"])),
        "configuration_sha256": digest(canonical(item["configuration"])),
        "status": "unavailable",
    }


def exists(directory, item):
    envelope = read(path(directory, item))
    if envelope is None:
        return False
    payload = _payload(item)
    if envelope != {"failure": payload, "sha256": digest(canonical(payload))}:
        raise ValueError("comparison failure receipt differs")
    return True


def record(directory, item):
    target = path(directory, item)
    if exists(directory, item):
        return
    payload = _payload(item)
    envelope = {"failure": payload, "sha256": digest(canonical(payload))}
    with staged(target, envelope) as temporary:
        temporary.chmod(0o400)
        os.link(temporary, target, follow_symlinks=False)
    sync(directory)
