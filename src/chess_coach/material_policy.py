"""Explicit promotion gate for independently validated material detector versions."""

MAPPER = "material-opportunity-mapper"
# An independent held-out evaluation must be documented before adding a version.
MASTERY_ELIGIBLE_VERSIONS: frozenset[str] = frozenset()


def mastery_allowed(row):
    if row["material_fact_count"] == 0:
        return row["mapping_producer"] != MAPPER
    version = row["material_min_version"]
    return version == row["material_max_version"] and version in MASTERY_ELIGIBLE_VERSIONS
