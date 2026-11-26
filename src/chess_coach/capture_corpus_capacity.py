"""Bound retained and in-progress prepared proof records together."""

LIMIT = 2000


def valid(data):
    prior = data.get("prior")
    if prior is not None and not isinstance(prior, dict):
        return False
    staged = {} if prior is None else prior.get("entries")
    return (
        isinstance(staged, dict)
        and len(data["entries"].keys() | staged.keys()) <= LIMIT
        and all(isinstance(key, str) and isinstance(value, dict) for key, value in staged.items())
    )


def reserve(data, building, key):
    existing, staged = data["entries"], data["prior"]["entries"]
    if key in existing.keys() | staged.keys():
        return False
    if len(existing.keys() | staged.keys()) < LIMIT:
        return True
    active = data.get("complete") or {}
    protected = set(active.get("keys", []) + (active.get("public") or {}).get("keys", []))
    protected.update(building["keys"] + building["public"]["keys"])
    protected.update(staged)
    evicted = max((key for key in existing if key not in protected), default=None)
    if evicted is None:
        building["incomplete"] = True
        return False
    del existing[evicted]
    return True
