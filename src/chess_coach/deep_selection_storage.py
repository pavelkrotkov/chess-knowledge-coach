"""Persist immutable selection generations and update their current pointer."""

from .deep_selection_replay import verify_replay
from .deep_selection_source import source_snapshot
from .fact_fingerprint import canonical, digest

SELECTOR_VERSION = "deep-selection-v1"


def persist_selection(db, source, learner, key, config, selected, coverage):
    fingerprint = digest(
        canonical(
            {
                "input": source["input_fingerprint"],
                "cheap_run_id": source["cheap_run_id"],
                "selector": SELECTOR_VERSION,
                "config": config,
            }
        )
    )
    if db.connection.in_transaction:
        raise RuntimeError("selection requires an idle database")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        fresh = source_snapshot(db, source["game"]["id"], learner)
        if (
            fresh["cheap_run_id"] != source["cheap_run_id"]
            or fresh["input_fingerprint"] != source["input_fingerprint"]
        ):
            raise ValueError("cheap analysis changed while selecting")
        selection_id = _insert_or_replay(db, source, key, config, coverage, selected, fingerprint)
        db.connection.execute(
            """INSERT INTO deep_selection_current(game_id,learner_key,selection_id) VALUES(?,?,?)
            ON CONFLICT(game_id,learner_key) DO UPDATE SET selection_id=excluded.selection_id""",
            (source["game"]["id"], key, selection_id),
        )
        db.connection.commit()
        return selection_id
    except BaseException:
        db.connection.rollback()
        raise


def _insert_or_replay(db, source, key, config, coverage, selected, fingerprint):
    game_id = source["game"]["id"]
    existing = db.connection.execute(
        "SELECT * FROM deep_selection_runs WHERE game_id=? AND learner_key=? AND selection_fingerprint=?",
        (game_id, key, fingerprint),
    ).fetchone()
    if existing is not None:
        verify_replay(db, existing, config, coverage, selected)
        return existing["id"]
    cursor = db.connection.execute(
        """INSERT INTO deep_selection_runs(game_id,learner_key,cheap_run_id,selector_version,
        input_fingerprint,selection_fingerprint,config_json,coverage_json)
        VALUES(?,?,?,?,?,?,?,?)""",
        (
            game_id,
            key,
            source["cheap_run_id"],
            SELECTOR_VERSION,
            source["input_fingerprint"],
            fingerprint,
            canonical(config),
            canonical(coverage),
        ),
    )
    selection_id = cursor.lastrowid
    if selection_id is None:
        raise RuntimeError("selection could not be stored")
    db.connection.executemany(
        """INSERT INTO deep_selection_items(selection_id,position_id,rank,allocation,reasons_json)
        VALUES(?,?,?,?,?)""",
        [
            (
                selection_id,
                item["position_id"],
                rank,
                item["allocation"],
                canonical(item["reasons"]),
            )
            for rank, item in enumerate(selected, 1)
        ],
    )
    return selection_id
