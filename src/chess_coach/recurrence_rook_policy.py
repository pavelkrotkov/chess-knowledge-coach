"""Validate the descriptive rook observation contract."""


def rook_ok(row, fact):
    return (
        (row["skill"], row["operation"], row["outcome"]) == ("open_files", "evaluate", "ambiguous")
        and fact["payload"].get("version") == "1.0.0"
        and fact["payload"].get("mastery_eligible") is False
    )
