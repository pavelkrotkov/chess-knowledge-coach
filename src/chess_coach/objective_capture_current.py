"""Require current, fully scoped owned material evidence."""

from .material_contract import SCOPE
from .material_contract import VERSION as MAPPER_VERSION
from .material_policy import MAPPER
from .unified_own_game_evidence import _inspect


def current(
    db, evidence_id, subject, *, kind="material_capture", operation="execute", _history=None
):
    view, review, reasons = _inspect(db, evidence_id, subject, history=_history)
    if reasons or view["objective"]["kind"] != kind:
        raise ValueError("capture source unavailable")
    row = db.connection.execute(
        "SELECT producer,mapper_version,subject,operation,position_id,scope_key,status FROM mapping_runs WHERE id=?",
        (view["lineage"]["mapping_run_id"],),
    ).fetchone()
    expected = (
        MAPPER,
        MAPPER_VERSION,
        view["subject"],
        operation,
        view["position_id"],
        SCOPE,
        "active",
    )
    if row is None or tuple(row) != expected:
        raise ValueError("capture source unavailable")
    return view, dict(review) if review else None


def require_protection_scope(db, evidence_id, subject, kind):
    if kind == "material_protection":
        current(db, evidence_id, subject, kind=kind, operation="prevent")
