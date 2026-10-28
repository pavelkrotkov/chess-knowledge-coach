"""Commit complete engine output and optional caller-owned checkpoint together."""

from contextlib import suppress

from .analysis_engine import create_run, scan
from .analysis_output import save_line


def run(db, game_id, binary, game, engine, config, nodes, depth, multipv, time_limit, on_complete):
    try:
        engine.configure({"Threads": config["threads"], "Hash": config["hash_mb"]})
        outputs = scan(
            db.connection,
            engine,
            game,
            nodes=nodes,
            depth=depth,
            multipv=multipv,
            time_limit=time_limit,
        )
        db.connection.execute("BEGIN IMMEDIATE")
        run_id = create_run(db.connection, game_id, binary, engine, config)
        for position, board, number, line in outputs:
            save_line(db.connection, run_id, position, board, number, line)
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
