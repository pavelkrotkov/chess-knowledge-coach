"""Show the named prevention scope without exposing its exemplar."""


def add_fields(result, row, provenance):
    if row["objective"] != "prevent_named_pin":
        return
    named = provenance["pin_prevention"]
    for key in ("origin", "attacker", "pinned", "rear", "kind"):
        result["pin_prevent_" + key] = named[key]
