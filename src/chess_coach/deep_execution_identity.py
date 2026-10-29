"""Determine whether recorded engines and neural-network provenance are comparable."""


def comparable_engine(cheap, deep):
    if not cheap.get("engine_sha256") or cheap.get("engine_sha256") != deep.get("engine_sha256"):
        return False
    identity = cheap.get("engine_id")
    if not isinstance(identity, dict) or not identity or identity != deep.get("engine_id"):
        return False
    return _same_networks(cheap, deep)


def _same_networks(cheap, deep):
    options = cheap.get("nnue_options")
    if not isinstance(options, dict) or options != deep.get("nnue_options"):
        return False
    if not options:
        return True
    # Existing cheap runs do not record external network file hashes.
    hashes = cheap.get("nnue_file_hashes")
    return (
        isinstance(hashes, dict)
        and bool(hashes)
        and all(hashes.values())
        and set(hashes) == set(options)
        and hashes == deep.get("nnue_file_hashes")
    )
