"""Resolve owner-bound, currently certified unified mate review items."""

from .curriculum_unified_corpus import candidate as corpus_candidate
from .curriculum_unified_identity import identity
from .curriculum_unified_owned import candidate as owned_candidate


def candidate(db, row, subject_hash, *, check=None):
    visible, ref = identity(row, subject_hash)
    if not visible:
        return False, None
    if row["source_type"] == "puzzle":
        from .curriculum_reference import referenced_candidate

        return True, referenced_candidate(db, ref)
    options = {"check": check} if check is not None else {}
    owned = owned_candidate(db, row, ref, **options)
    if owned is not None:
        return owned
    return corpus_candidate(db, ref)


def prompt(db, row, subject_hash, *, check=None):
    visible, ref = identity(row, subject_hash)
    if not visible:
        return False, None
    if row["source_type"] == "puzzle":
        from .curriculum_prompt_reference import referenced_prompt

        return True, referenced_prompt(db, ref)
    options = {"check": check} if check is not None else {}
    _, result = candidate(db, row, subject_hash, **options)
    return True, result["prompt_key"] if result else None
