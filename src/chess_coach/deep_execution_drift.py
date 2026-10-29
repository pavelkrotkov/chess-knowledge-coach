"""Flag large native score changes as search instability, not a skill claim."""

import json

from .deep_selection_wdl import _expected_score

CP_DRIFT = 100
WDL_DRIFT = 0.15


def score_drift(old, new):
    if old["score_kind"] == "cp" and abs(old["score_value"] - new["score_value"]) >= CP_DRIFT:
        return True
    if old["score_kind"] == "mate" and (old["score_value"] > 0) != (new["score_value"] > 0):
        return True
    left, right = _expected_score(old["wdl"]), _expected_score(_wdl(new))
    return left is not None and right is not None and abs(left - right) >= WDL_DRIFT


def _wdl(line):
    try:
        return json.loads(line["wdl_json"]) if line["wdl_json"] else None
    except (TypeError, ValueError):
        return None
