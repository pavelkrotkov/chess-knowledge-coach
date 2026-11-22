"""Bind a worked prevention example to the exact public source history."""

from .fact_fingerprint import canonical, digest
from .opening_public_proof_replay import _attribution


def bind(db, row, binding, identity, moves, first, last, ply, board, recorded, example):
    example.update(
        {
            "ply": ply,
            "window_start": first,
            "window_end": last,
            "recorded_uci": recorded.uci(),
            "recorded_san": board.san(recorded),
            "history_sha256": digest(canonical(moves[: ply - 1])),
            "full_history_sha256": digest(canonical(moves)),
            "source_identity": identity,
            "record_ended_in_window": row[1] <= last,
            "board_terminal_at_record_end": None,
        }
    )
    source = {**binding, "index_sha256": binding["policy"]["prevention"]["index_sha256"]}
    _attribution(db, row[0], row[2], source, example)
