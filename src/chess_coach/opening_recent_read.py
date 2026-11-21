"""Recheck the private immutable prefix and its bounded provenance receipt."""

import codecs
import hashlib
import os
import stat

from .opening_recent_receipt import receipt
from .opening_recent_source import PREFIX_BYTES, PREFIX_NAME
from .opening_reference_decode import decode


def _hash(path):
    if path.is_symlink():
        raise ValueError("recent source prefix unavailable")
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o777 != 0o400
    ):
        raise ValueError("recent source prefix unavailable")
    if info.st_size != PREFIX_BYTES:
        raise ValueError("recent source prefix size differs")
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def source(directory):
    value = receipt(directory)
    path = directory / PREFIX_NAME
    if _hash(path) != value.get("prefix_sha256"):
        raise ValueError("recent source prefix digest differs")
    return path, value


def text(directory):
    path, value = source(directory)
    with path.open("rb") as stream:
        content, _ = decode(stream, allow_partial=True)
    if _hash(path) != value["prefix_sha256"]:
        raise ValueError("recent source prefix changed")
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    return decoder.decode(content, final=False), value
