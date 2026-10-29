"""Derive provisional mapping operations from witnessed observations."""


def outcomes(fact):
    roots = [root for root in fact["attack"].get("alternatives", []) if root["status"] == "proved"]
    result = []
    if roots:
        played = any(root["move"]["uci"] == fact["played"] for root in roots)
        result.append(("execute", "success" if played else "ambiguous"))
    defense = fact["defense"]
    if defense.get("status") == "opportunity":
        result.append(("prevent", "success" if defense["outcome"] == "avoids" else "failure"))
    return result


def status(fact):
    return "opportunity" if outcomes(fact) else "unknown"
