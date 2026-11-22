"""Track optional fork coverage in the shared preparation."""

from .opening_public_fork_stats import add, empty


def start(binding, result, selected):
    if "fork" not in binding["policy"]:
        return None
    result["forks"] = empty(selected)
    return {"proofs": 0}


def failed(result, budget):
    if budget is not None:
        result["forks"]["attempted"] += 1
        result["forks"]["unsupported"] += 1


def record(result, budget, item):
    if budget is not None:
        add(result["forks"], item)


def finish(result, budget, selected):
    if budget is None:
        return
    forks = result["forks"]
    forks["incomplete"] += selected - forks["attempted"]
    forks["interrupted"] = result["interrupted"]
    forks["censored"] = result["censored"]
    forks["proofs"] = budget["proofs"]
