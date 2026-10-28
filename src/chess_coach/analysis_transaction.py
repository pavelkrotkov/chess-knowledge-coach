"""Commit complete engine output and optional caller-owned checkpoint together."""

import json
from contextlib import suppress
from tempfile import TemporaryFile

from .analysis_engine import create_run, scan
from .analysis_output import save_fields


def run(db, game_id, binary, game, engine, config, nodes, depth, multipv, time_limit, on_complete):
    try:
        engine.configure({"Threads": config["threads"], "Hash": config["hash_mb"]})
        with TemporaryFile(mode="w+t", encoding="utf-8", dir=db.path.parent) as spool:
            scan(
                db.connection,
                engine,
                game,
                spool,
                nodes=nodes,
                depth=depth,
                multipv=multipv,
                time_limit=time_limit,
            )
            spool.seek(0)
            db.connection.execute("BEGIN IMMEDIATE")
            run_id = create_run(db.connection, game_id, binary, engine, config)
            for line in spool:
                save_fields(db.connection, run_id, json.loads(line))
            if on_complete is not None:
                on_complete(db.connection, run_id)
            engine.quit()
            db.connection.commit()
        return run_id
    except BaseException:
        db.connection.rollback()
        with suppress(Exception):
            engine.quit()
        with suppress(Exception):
            engine.close()
        raise
