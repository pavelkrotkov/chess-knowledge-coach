"""Select the stored proof for the completed supplied pin line."""

import json


def certificate(row, binding):
    selected = binding["selected_line_indices"]
    lines = json.loads(row["lines_json"])
    candidates = json.loads(row["candidates_json"])
    index = next(
        item
        for item in candidates
        if type(item) is int and 0 <= item < len(lines) and len(lines[item]) == row["next_index"]
    )
    original = selected[index]
    certificate = next(
        item for item in binding["candidate_certificates"] if item["line_index"] == original
    )
    if certificate["branch"]["move"] != lines[index][0]:
        raise ValueError("pin contrast line changed")
    return certificate
