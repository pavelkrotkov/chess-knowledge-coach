"""Resolve optional shared detector inputs and preserve exact replay bytes."""


def values(connection, input_hash, input_json, *, legacy=False):
    if legacy:
        return input_json
    setting = connection.execute(
        "SELECT compact FROM detector_input_settings WHERE id=1"
    ).fetchone()
    if setting is None:
        raise ValueError("detector input setting unavailable")
    if not setting[0]:
        return input_json
    connection.execute(
        "INSERT OR IGNORE INTO detector_inputs(input_hash,input_json) VALUES(?,?)",
        (input_hash, input_json),
    )
    row = connection.execute(
        "SELECT input_json FROM detector_inputs WHERE input_hash=?", (input_hash,)
    ).fetchone()
    if row is None or row[0] != input_json:
        raise ValueError("detector input identity conflict")
    return ""
