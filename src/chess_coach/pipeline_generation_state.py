"""Identify interrupted generations superseded by another producer."""

import sqlite3

from .tactical_mapping import PRODUCER as MAPPER
from .tactical_opportunities import PRODUCER


def superseded(connection: sqlite3.Connection, game_id: int, stage: str, generation: int) -> bool:
    if stage in {"structures", "opening"}:
        table = {"structures": "structure_runs", "opening": "opening_runs"}[stage]
        return (
            connection.execute(
                f"SELECT 1 FROM {table} WHERE game_id=? AND pipeline_generation=? AND status=? LIMIT 1",
                (game_id, generation, "superseded"),
            ).fetchone()
            is not None
        )
    if stage == "tactical":
        return _tactical_superseded(connection, game_id, generation)
    return False


def _tactical_superseded(connection: sqlite3.Connection, game_id: int, generation: int) -> bool:
    for table, path, producer in (
        ("detector_runs", "$.detector_input.pipeline_generation", PRODUCER),
        ("mapping_runs", "$.pipeline_generation", MAPPER),
    ):
        row = connection.execute(
            f"""SELECT 1 FROM {table} r JOIN positions p ON p.id=r.position_id
            WHERE p.game_id=? AND r.status=? AND r.producer=?
            AND json_extract(r.input_json,?)=? LIMIT 1""",
            (game_id, "superseded", producer, path, generation),
        ).fetchone()
        if row is not None:
            return True
    return False
