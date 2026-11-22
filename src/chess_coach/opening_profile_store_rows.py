"""Write existing ordered profile rows and optional original histories."""

import json
import time


def write(db, records, *, history, deadline):
    for item in records:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("reference build deadline")
        identity, number, context, site, positions, _, total = item[:7]
        if history:
            db.execute(
                "INSERT INTO histories VALUES (?,?,?)",
                (number, identity, json.dumps(item[7], separators=(",", ":"))),
            )
        db.execute("INSERT INTO games VALUES (?,?,?,?)", (number, json.dumps(context), site, total))
        db.executemany(
            "INSERT INTO moves VALUES (?,?,?,?,?,?)",
            [
                (number, ply, parent, san, uci, json.dumps(shapes))
                for ply, parent, san, uci, shapes in positions
            ],
        )
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("reference build deadline")
