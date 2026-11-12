"""Show the named material cue without exposing the defensive move."""


def add_fields(result, row, provenance):
    if row["source_version"] == "discovery-material-defense-own-v1":
        result["discovery_target"] = provenance["discovery_target"]
        result["discovery_slider"] = provenance["discovery_slider"]
        result["discovery_move"] = provenance["discovery_move"]
