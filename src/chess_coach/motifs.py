"""Record tactical motif opportunities with immutable provenance."""

from .db import Database
from .motif_detectors import DETECTOR_VERSION, detect_motifs
from .motif_mapping import persist_motifs

MAPPER_VERSION = "0.1.0"

__all__ = ["detect_motifs", "record_motif_opportunities"]


def record_motif_opportunities(
    db: Database,
    position_id: int,
    *,
    detector_version: str = DETECTOR_VERSION,
    mapper_version: str = MAPPER_VERSION,
    operation: str = "prevent",
    outcome: str = "ambiguous",
    outcomes: dict[str, str] | None = None,
) -> int:
    """Persist facts and mappings in one transaction without inferring cognition."""
    return persist_motifs(
        db,
        position_id,
        detector_version=detector_version,
        mapper_version=mapper_version,
        operation=operation,
        outcome=outcome,
        outcomes=outcomes,
    )
