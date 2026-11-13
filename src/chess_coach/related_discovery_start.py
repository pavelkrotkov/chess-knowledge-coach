"""Admit one preselected discovered-mate assessment."""

from .related_discovery import selection
from .related_discovery_contract import KEY, VERSION
from .related_session_start import start_selected
from .related_transfer_admission import admit


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, reference):
    chosen = selection(db, subject, evidence_id, corpus_version)
    selected = admit(chosen, reference, VERSION, "discovery_mate")
    selected[3]["game_watermark"], selected[3]["legacy_watermark"] = chosen[2]["frontier"]
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key=KEY,
        resolver=lambda: selected,
    )
