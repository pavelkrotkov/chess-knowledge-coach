"""Revalidate one owner-bound canonical promotion offer at actual start."""

from .curriculum_canonical_context import context
from .curriculum_canonical_cursor import policy_binding
from .curriculum_cursor import revision
from .curriculum_cursor_values import integer
from .curriculum_prerequisite_launch import bounded
from .curriculum_prerequisite_source import graph
from .curriculum_prerequisite_token import _decode, encode
from .curriculum_public_source import prompt_key
from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .tactical_exposure_practice import check as exposure
from .unified_source_current import snapshot_hash
from .unified_sources import resolve_source


def issue(db, state, item):
    binding = digest(canonical([state["canonical_scope"], item["exposure_state"]]))
    return encode(
        db,
        [
            state["mix_policy"],
            graph(),
            state["subject_hash"],
            [item["source_version"], item["source_key"]],
            item["source_snapshot_hash"],
            digest(item["prompt_key"]),
            state["revision"],
            binding,
            state["scan_limit"],
        ],
    )


def _validate(db, subject, version, key, token, check):
    policy, graph_hash, owner, source, fingerprint, prompt, rev, binding, limit = _decode(db, token)
    identity = normalize_identity(subject)
    if (
        identity is None
        or (policy, graph_hash, owner, source, rev)
        != (policy_binding(), graph(), digest(identity), [version, key], revision(db))
        or not integer(limit, 1, 1000)
    ):
        raise ValueError("canonical plan changed")
    current = context(db, identity, limit, check)
    if current["scope"] is None:
        raise ValueError("canonical practice context unavailable")
    snapshot = resolve_source(db, "public", version, key, subject=subject)
    key_fen = prompt_key(snapshot["prompt_fen"])
    if (snapshot_hash(snapshot), digest(key_fen)) != (fingerprint, prompt):
        raise ValueError("canonical source changed")
    history = exposure(db, identity, key_fen)
    if (
        history not in {"clear", "history_unknown"}
        or digest(canonical([current["scope"], history])) != binding
    ):
        raise ValueError("canonical context or exposure changed")
    check()


def validate_start(db, subject, version, key, token, budget):
    bounded(budget, lambda check: _validate(db, subject, version, key, token, check))
