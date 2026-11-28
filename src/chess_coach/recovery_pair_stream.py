"""Write and independently compare bounded gzip recovery archives."""

import gzip
import hashlib

from .recovery_gzip_stream import CHUNK
from .recovery_pair_archive import check_archive


def compare(path, archive, raw, size, expected_hash, deadline, check):
    check_archive(path, archive, deadline)
    check()
    raw.seek(0)
    digest = hashlib.sha256()
    total = 0
    with gzip.open(path, "rb") as decoded:
        while chunk := decoded.read(CHUNK):
            check()
            total += len(chunk)
            if total > size or raw.read(len(chunk)) != chunk:
                raise ValueError("offline archive bytes differ")
            digest.update(chunk)
        check()
    if total != size or raw.read(1) or digest.hexdigest() != expected_hash:
        raise ValueError("offline archive length or hash differs")
    deadline.check()


def raw_digest(raw, deadline, check):
    digest = hashlib.sha256()
    raw.seek(0)
    while chunk := raw.read(CHUNK):
        check()
        digest.update(chunk)
    deadline.check()
    return digest.hexdigest()
