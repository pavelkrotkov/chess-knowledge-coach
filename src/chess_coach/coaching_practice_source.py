"""Resolve an exact, current practice source for a coaching lesson."""

from .coaching_practice_identity import identity
from .lesson_source import source
from .unified_sources import resolve_source


def resolve_example(
    db, subject, lesson, example, *, identity_for=None, _snapshots=None, check=None
):
    evidence_id, position = example["evidence_id"], example["position_id"]
    options = {"check": check} if check is not None else {}
    inspected = source(db, subject, {"id": evidence_id, "position_id": position}, **options)
    if not inspected:
        return None
    evidence = inspected["evidence"]
    if not _matches(evidence, lesson):
        return None
    version, key, kind = (identity_for or identity)(db, subject, evidence)
    # The checked fork path must not create a second proof deadline.
    snapshot = _resolve(db, subject, version, key, kind, check)
    if (
        snapshot["prompt_fen"] != example["fen"]
        or snapshot["provenance"]["evidence_id"] != evidence_id
    ):
        return None
    if _snapshots is not None:
        _snapshots.append(snapshot)
    return {
        "version": version,
        "key": key,
        "kind": kind,
        "evidence_id": evidence_id,
        "position_id": position,
    }


def available(db, subject, lesson, examples, resolver, snapshots=None):
    for example in examples:
        try:
            options = {"_snapshots": snapshots} if snapshots is not None else {}
            result = resolver(db, subject, lesson, example, **options)
        except (ValueError, KeyError, TypeError, IndexError):
            continue
        if result:
            yield result


def _resolve(db, subject, version, key, kind, check):
    if check is not None and kind == "fork":
        from .objective_fork_source import resolve

        return resolve(db, version, key, subject, check=check)
    return resolve_source(db, "own-game", version, key, subject=subject)


def _matches(evidence, lesson):
    return (
        evidence["skill"],
        evidence["operation"],
        evidence["mapping_producer"],
        evidence["outcome"],
    ) == (lesson["skill"], lesson["operation"], lesson["family"], "failure") and evidence["facts"][
        0
    ]["detector_version"] == lesson["source_version"]
