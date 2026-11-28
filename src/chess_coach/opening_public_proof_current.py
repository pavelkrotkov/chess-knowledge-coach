"""Read or confirm a window's current source binding."""

from .opening_public_fork_later import bound as full_bound
from .opening_public_proof_source import binding, check
from .opening_public_proof_versions import current as current_preparation
from .opening_public_proof_window import choose
from .style_schedule_budget import history_budget


def selected(directory, identity, root, subject, deadline, window, *, kind="fork"):
    if kind not in {
        "fork",
        "prevention",
        "mate",
        "short_mate",
        "back_rank",
        "created_backrank",
        "skewer",
        "double_mate",
        "discovery_material",
        "discovery_opportunity",
    }:
        raise ValueError("invalid proof kind")
    if window == "initial" and kind == "fork":
        return (*current_preparation(directory, identity), None)
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid fork window")
    try:
        full = full_bound(root, subject, deadline)
    except (OSError, ValueError, TypeError, KeyError):
        return (*current_preparation(directory, identity, capture_only=True), None)
    chosen = choose(identity, full, kind, window)
    value, legacy = current_preparation(directory, identity, chosen=chosen)
    return value, legacy, full


def confirm(
    db, root, subject, game_id, position_id, alternative, deadline, base, index, full, version
):
    check(deadline)
    with history_budget(deadline=deadline):
        current, actual = binding(db, root, subject, game_id, position_id, alternative, deadline)
    if current != base or actual != index:
        raise ValueError("public preparation source changed")
    if full and full_bound(root, subject, deadline) != full:
        raise ValueError("full history reference changed")
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("owned decision changed")
