"""Private cache path and current proof-policy binding."""

from pathlib import Path

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .mate_proof import MAX_NODES
from .mate_proof import VERSION as PROOF_VERSION
from .mate_proof_search import MAX_REPLIES

VERSION = "short-mate-game-trend-v1"


def location(db, root):
    if not root:
        return None
    try:
        root = Path(root).resolve(strict=True)
        data = (root / ".runtime" / "data").resolve(strict=True)
        path = Path(db.path).resolve(strict=True)
        if not data.is_relative_to(root) or not path.is_relative_to(data) or not path.is_file():
            return None
        return path.with_name(path.name + ".short-mate-trend.json")
    except (OSError, ValueError, TypeError):
        return None


def binding(db, learner):
    path = Path(db.path).resolve(strict=True)
    stat = path.stat()
    subject = normalize_identity(learner)
    if not subject:
        raise ValueError("learner identity is unavailable")
    return digest(
        canonical(
            [
                VERSION,
                PROOF_VERSION,
                MAX_NODES,
                MAX_REPLIES,
                0.5,
                str(path),
                stat.st_dev,
                stat.st_ino,
                subject,
            ]
        )
    )
