"""Sign and recheck one owner-bound public mate plan offer."""

from .curriculum_cursor import revision
from .curriculum_prerequisite_source import graph
from .curriculum_prerequisite_token import _decode, encode
from .curriculum_public_cursor import POLICY
from .curriculum_public_source import prompt_key
from .fact_fingerprint import digest
from .learner_identity import normalize_identity
from .tactical_course_budget import PreviewUnavailable
from .tactical_exposure_practice import check as exposure
from .unified_source_current import snapshot_hash
from .unified_sources import resolve_source


def issue(db, state, item):
    return encode(
        db,
        [
            POLICY,
            graph(),
            state["subject_hash"],
            item["source_version"],
            item["source_key"],
            item["source_snapshot_hash"],
            digest(item["prompt_key"]),
            state["revision"],
            item["exposure_state"],
        ],
    )


def _validate(db, subject, version, key, token, check):
    policy, graph_hash, owner, source_version, source_key, fingerprint, prompt, rev, history = (
        _decode(db, token)
    )
    identity = normalize_identity(subject)
    if identity is None or (policy, graph_hash, owner, source_version, source_key, rev) != (
        POLICY,
        graph(),
        digest(identity),
        version,
        key,
        revision(db),
    ):
        raise ValueError("public plan changed")
    check()
    snapshot = resolve_source(db, "public", version, key, subject=subject)
    key_fen = prompt_key(snapshot["prompt_fen"])
    if (snapshot_hash(snapshot), digest(key_fen)) != (fingerprint, prompt):
        raise ValueError("public source changed")
    if history not in {"clear", "history_unknown"} or exposure(db, identity, key_fen) != history:
        raise ValueError("public exposure changed")
    check()


def validate_start(db, subject, version, key, token, budget):
    from .curriculum_canonical_cursor import POLICY as CANONICAL_POLICY

    # The signed policy selects the exact objective, rather than guessing from the source type.
    policy = _decode(db, token)[0]
    if isinstance(policy, str) and policy.startswith(CANONICAL_POLICY + ":"):
        from .curriculum_canonical_launch import validate_start as canonical_start

        return canonical_start(db, subject, version, key, token, budget)
    try:
        with budget.scope(snapshot=False):
            _validate(db, subject, version, key, token, budget.check)
    except PreviewUnavailable:
        raise ValueError("public plan launch unavailable") from None
