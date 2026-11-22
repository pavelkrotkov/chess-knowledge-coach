"""Count complete and budget-limited public fork games."""


def empty(selected):
    return {
        "selected": selected,
        "analyzed": 0,
        "unsupported": 0,
        "incomplete": 0,
        "attempted": 0,
        "root_limit": 0,
        "proof_limit": 0,
        "roots": 0,
        "geometries": 0,
        "material": 0,
        "mate": 0,
        "example": None,
    }


def add(result, item):
    result["attempted"] += 1
    result["analyzed"] += int(not item["incomplete"])
    result["incomplete"] += int(item["incomplete"])
    result["unsupported"] += int(bool(item["unsupported"]))
    result["root_limit"] += int(item["limit"] == "roots")
    result["proof_limit"] += int(item["limit"] == "proofs")
    for key in ("roots", "geometries", "material", "mate"):
        result[key] += item[key]
    if result["example"] is None:
        result["example"] = item["example"]
