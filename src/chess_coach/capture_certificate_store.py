"""Bounded, checksummed worker certificates for exact owned captures."""

from .capture_game_trend_paths import binding as material_binding
from .capture_game_trend_paths import location as trend_location
from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .material_contract import CAPTURE_VERSION
from .material_contract import VERSION as MATERIAL_VERSION
from .objective_capture_contract import TARGET_OBJECTIVE
from .objective_capture_judge import VERSION as JUDGE_VERSION
from .objective_contract import OWNED_HISTORY
from .short_mate_trend_store import read, write

POLICY = (
    "owned-capture-certificate-v1",
    JUDGE_VERSION,
    TARGET_OBJECTIVE,
    OWNED_HISTORY,
    CAPTURE_VERSION,
    MATERIAL_VERSION,
)
LIMIT = 20


def location(db, root, subject):
    base = trend_location(db, root)
    owner = normalize_identity(subject)
    if base is None or not owner:
        return None
    suffix = digest(owner)
    return base.with_name(db.path.name + ".capture-cert-" + suffix + ".json")


# Material binding already includes the database identity and bounded proof limits.
def binding(db, subject):
    return digest(canonical([POLICY, material_binding(db, subject)]))


def _valid(data, expected):
    entries = data.get("certificates")
    return (
        data.get("binding") == expected
        and isinstance(entries, dict)
        and len(entries) <= LIMIT
        and all(isinstance(key, str) and isinstance(value, dict) for key, value in entries.items())
    )


def load(db, root, subject):
    path = location(db, root, subject)
    return read(path, binding(db, subject), validator=_valid) if path is not None else None


def publish(db, root, subject, certificates):
    path = location(db, root, subject)
    if path is None:
        raise ValueError("capture certificate scope unavailable")
    data = {"binding": binding(db, subject), "certificates": certificates}
    if not _valid(data, data["binding"]):
        raise ValueError("capture certificates unavailable")
    write(path, data)
