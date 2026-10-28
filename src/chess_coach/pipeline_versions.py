"""Validate explicit learner attribution and producer versions."""

from .learner_identity import normalize_identity


def validate_versions(config) -> None:
    if bool(config.opening_version) != bool(config.opening_source):
        raise ValueError("opening version and source must be supplied together")
    if not all(
        isinstance(v, str) and v.strip()
        for v in (
            config.engine_path,
            config.structure_version,
            config.classifier_version,
            config.ontology_version,
            config.tactical_version,
        )
    ):
        raise ValueError("pipeline paths and versions must be nonempty")


def validate_learner(value) -> None:
    if not isinstance(value, str) or normalize_identity(value) in {None, "unassigned"}:
        raise ValueError("an explicit learner is required")
