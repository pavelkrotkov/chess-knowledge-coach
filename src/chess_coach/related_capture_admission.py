"""Resolve opaque references to current capture transfer sources."""

from .related_capture import VERSION, _selection
from .related_transfer_admission import admit as admit_selection


def admit(db, subject, position, corpus_version, reference):
    selection = _selection(db, subject, position, corpus_version)
    return admit_selection(selection, reference, VERSION, "material_capture")
