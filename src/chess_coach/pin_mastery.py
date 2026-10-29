"""Keep every pin-family source ineligible pending independent qualification."""


def closed(row):
    return (
        row["skill"] in {"absolute_pin", "relative_pin"}
        or row["mapping_producer"] in {"pin-execute-mapper", "pin-prevent-mapper"}
        or row["pin_fact_count"]
    )
