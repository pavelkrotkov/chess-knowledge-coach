"""Import chapters with durable reconciliation and final verification."""

from .study_import_one import upload_one
from .study_import_verify import finish
from .study_pgn_verify import matches
from .tactical_study_pgn import matches_mainline


def upload_all(remote, path, state, chapters, *, check=lambda: None, strict=False):
    match = matches_mainline if strict else matches
    for index, chapter in enumerate(chapters):
        upload_one(remote, path, state, chapter, index, chapters, check, match, strict)
    finish(remote, path, state, chapters, check, match, strict)
