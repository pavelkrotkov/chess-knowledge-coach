"""Bounded, pinned local broadcast input for the reference sample."""

import codecs
import hashlib
import os
from pathlib import Path

from .opening_reference_decode import decode as _decode

SOURCE = "https://database.lichess.org/#broadcasts"
SOURCE_ARCHIVE = "https://database.lichess.org/broadcast/lichess_db_broadcast_2026-09.pgn.zst"
SOURCE_MONTH = "2026-09"
TRANSFORM = "v1:32MB-decoded;5000-records;1000-games;40-opening-plies;512-game-plies"
LICENSE = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
SOURCE_NAME = "opening-reference-source-2026-09.pgn.zst"
SOURCE_BYTES = 18_414_369
SOURCE_SHA256 = "27a39d035767a30901b89602f33f2a7b27d4ab5025842071165fa079f8fff1df"


def _digest(file):
    file.seek(0)
    return hashlib.file_digest(file, "sha256").hexdigest()


def read(path):
    with Path(path).open("rb") as file:
        info = os.fstat(file.fileno())
        if info.st_size != SOURCE_BYTES or _digest(file) != SOURCE_SHA256:
            raise ValueError("reference archive does not match the pinned source")
        file.seek(0)
        content, truncated = _decode(file)
        if _digest(file) != SOURCE_SHA256:
            raise ValueError("reference archive changed during import")
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    return decoder.decode(content, final=not truncated), truncated
