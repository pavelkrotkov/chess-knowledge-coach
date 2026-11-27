"""Recheck a signed untimed common-choice offer at the learning boundary."""

from .curriculum_capture_offer_check import _bounded
from .curriculum_capture_offer_scope import require_revision, scope
from .curriculum_common_inputs import offer_current
from .curriculum_cursor_values import text
from .curriculum_priority_validate import _capture_input
from .curriculum_window_offer_check import valid_time
from .learner_identity import normalize_identity
from .mastery_time import parse_utc


def check(db, data, subject, source, version, key, mode, root, budget):
    owner = normalize_identity(subject)
    scope(data, owner, source, version, key, mode)
    if root is None or budget is None:
        raise ValueError("common practice offer changed")
    from .curriculum_capture_offer import COMMON_WINDOW_POLICY

    window = data[0] == COMMON_WINDOW_POLICY
    binding = _binding(db, data[7], window=window)
    if window:
        _capture_input(binding["window_scope"])
    files = _bounded(budget, lambda: offer_current(db, owner, binding, root, budget.check))
    valid_time(data)
    return {"data": data, "subject": owner, "root": root, "files": files, "common": True}


def _binding(db, binding, *, window=False):
    fields = {"revision", "common_input", "corpus_version", "as_of"}
    if window:
        fields.add("window_scope")
    if not isinstance(binding, dict) or set(binding) != fields:
        raise ValueError("common practice offer changed")
    require_revision(db, binding["revision"])
    if not text(binding["corpus_version"], 256) or parse_utc(binding["as_of"]) is None:
        raise ValueError("common practice offer changed")
    _capture_input(binding["common_input"])
    return binding
