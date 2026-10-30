"""Bind explicit public promotion metadata to immutable task identity."""

from .fact_fingerprint import canonical, digest
from .objective_contract import STANDALONE
from .objective_promotion_contract import OBJECTIVES, VERSION


def decorate(provenance, row, candidate, version, key):
    if candidate["objective"] in OBJECTIVES:
        provenance.update(
            {
                "objective_version": VERSION,
                "history_mode": STANDALONE,
                "source_fingerprint": digest(
                    canonical({"version": version, "key": key, "task": row})
                ),
            }
        )
