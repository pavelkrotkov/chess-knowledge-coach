"""Only the independently reviewed capture source and operation are eligible."""

import pytest

from chess_coach.material_policy import fact_allowed


def approved():
    return {
        "producer": "material-opportunity",
        "fact_type": "material_opportunity",
        "detector_version": "1.1.0",
        "run_detector_version": "1.1.0",
        "payload": {"kind": "material_capture", "outcome": "failure"},
    }


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_exact_capture_source_and_outcome_are_approved(outcome):
    fact = approved()
    fact["payload"]["outcome"] = outcome
    assert fact_allowed(fact, skill="hanging_piece", operation="execute", outcome=outcome)


@pytest.mark.parametrize(
    "change",
    [
        {"producer": "other"},
        {"fact_type": "other"},
        {"detector_version": "1.0.0"},
        {"detector_version": "1.0.0", "run_detector_version": "1.0.0"},
        {"detector_version": None},
        {"run_detector_version": "1.0.0"},
        {"run_detector_version": None},
        {"payload": None},
        {"payload": {}},
        {"payload": {"kind": [], "outcome": "failure"}},
        {"payload": {"kind": "unknown", "outcome": "failure"}},
        {"payload": {"kind": "material_capture", "outcome": "success"}},
    ],
)
def test_capture_source_mismatch_is_closed(change):
    assert not fact_allowed(
        {**approved(), **change}, skill="hanging_piece", operation="execute", outcome="failure"
    )


@pytest.mark.parametrize(
    ("skill", "operation", "outcome"),
    [
        ("fork", "execute", "failure"),
        ("hanging_piece", "prevent", "failure"),
        ("hanging_piece", "execute", "ambiguous"),
    ],
)
def test_capture_wrong_mapping_is_closed(skill, operation, outcome):
    assert not fact_allowed(approved(), skill=skill, operation=operation, outcome=outcome)
