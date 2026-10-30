"""Synthetic mover-perspective WDL intervals and immutable pawn continuations."""

import json

import chess
import chess.syzygy
import pytest

from chess_coach import pawn_proof, pawn_tables
from chess_coach.db import Database
from chess_coach.objective_pawn_bounds import verdict
from chess_coach.objective_pawn_contract import VERSION
from chess_coach.objective_pawn_judge import judge
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.pawn_coach_detector import process_decision
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_mate_proof import owned_game

FEN = "8/8/8/8/2k5/4K3/3P4/8 w - - 0 1"
SUBJECT = "fixture_a"


def synthetic_proof(board, *, goal=1):
    values = {"e3e4": (goal, goal), "e3f3": (goal, goal), "d2d4": (-1, -1), "e3f4": (0, 1)}
    return {
        "status": "complete",
        "lower": goal,
        "upper": goal,
        "nodes": 10,
        "alternatives": [
            {
                "move": {"uci": m.uci(), "san": board.san(m)},
                "lower": values.get(m.uci(), (-1, 1))[0],
                "upper": values.get(m.uci(), (-1, 1))[1],
            }
            for m in board.legal_moves
        ],
    }


def setup_game(path, monkeypatch):
    board = chess.Board(FEN)
    proof = synthetic_proof(board)
    db = owned_game(path, monkeypatch, fen=FEN, move="d4")
    monkeypatch.setattr("chess_coach.pawn_inspection.inspect", lambda board: proof)
    evidence = process_decision(db, 1, SUBJECT)["evidence_ids"][0]

    def evaluate(position, **kwargs):
        if position.turn == chess.WHITE and not position.move_stack:
            return proof
        if position.turn == chess.WHITE:
            return {
                "status": "complete",
                "lower": 1,
                "upper": 1,
                "nodes": 10,
                "alternatives": [
                    {"move": {"uci": move.uci()}, "lower": 1, "upper": 1}
                    for move in position.legal_moves
                ],
            }
        return {
            "status": "complete",
            "lower": -1,
            "upper": -1,
            "nodes": 10,
            "alternatives": [
                {"move": {"uci": move.uci()}, "lower": -1, "upper": -1}
                for move in position.legal_moves
            ],
        }

    monkeypatch.setattr(pawn_proof, "inspect_reused", evaluate)
    return db, evidence


def begin(db, evidence, attempt):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def data():
    return {
        "proof_version": pawn_proof.VERSION,
        "proof_manifest_sha256": pawn_tables.MANIFEST_SHA256,
    }


@pytest.mark.parametrize(
    "low,high,goal,status",
    [
        (1, 1, 1, "correct"),
        (0, 1, 1, "unresolved"),
        (-1, 0, 1, "incorrect"),
        (0, 1, 0, "correct"),
        (-1, 0, 0, "unresolved"),
        (-1, -1, 0, "incorrect"),
    ],
)
def test_interval_goal_semantics(low, high, goal, status):
    assert verdict(low, high, goal)[0] == status


@pytest.mark.parametrize("black", [False, True])
def test_result_proof_preserves_mover_perspective(monkeypatch, black):
    board = chess.Board(FEN)
    if black:
        board = board.mirror()
    move = next(iter(board.legal_moves))
    report = {
        "status": "complete",
        "lower": 1,
        "upper": 1,
        "nodes": 1,
        "alternatives": [{"move": {"uci": move.uci()}, "lower": 1, "upper": 1}],
    }
    monkeypatch.setattr(pawn_proof, "inspect_reused", lambda board, **kw: report)
    result = judge(board, move, 1, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["status"] == "correct" and result["goal"] == 1
    assert result["continuation"]["status"] == "unavailable"


def test_owned_unlisted_result_and_legal_training_continuation(tmp_path, monkeypatch):
    db, evidence = setup_game(tmp_path / "pawn.sqlite", monkeypatch)
    tracked = ("evidence_mappings", "mastery_events", "training_items", "training_attempts")
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    }
    state = begin(db, evidence, "pawn")
    assert state["objective"] == "preserve_pawn_win"
    original = submit(db, "pawn", SUBJECT, event_id="answer", move="e3f3")
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
    ).fetchone()[0]
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["continuation"]["status"] == "available"
    resumed = show(db, "pawn", SUBJECT)
    assert resumed["status"] == "active" and resumed["pawn_continuation"]
    board = chess.Board(resumed["fen"])
    next_move = next(iter(board.legal_moves)).uci()
    event = submit(db, "pawn", SUBJECT, event_id="continue", move=next_move)
    assert event["feedback"] == "needs_verification" and event["status"] == "needs_verification"
    pending = show(db, "pawn", SUBJECT)
    assert (
        pending["status"] == "needs_verification" and pending["verification"]["status"] == "pending"
    )
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "pawn", "continue")["status"] == "correct"
    assert show(db, "pawn", SUBJECT)["pawn_continuation"]
    assert submit(db, "pawn", SUBJECT, event_id="answer", move="e3f3") == original
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
        ).fetchone()[0]
        == frozen
    )
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    } == before


def test_unknown_intervals_and_unavailable_continuation_do_not_invent_a_result(
    tmp_path, monkeypatch
):
    db, evidence = setup_game(tmp_path / "unknown.sqlite", monkeypatch)
    begin(db, evidence, "unknown")
    submit(db, "unknown", SUBJECT, event_id="move", move="e3f4")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    assert inspect(db, SUBJECT, "unknown", "move")["reason"] == "result_interval_overlaps_goal"
    begin(db, evidence, "worse")
    submit(db, "worse", SUBJECT, event_id="move", move="d2d4")
    assert process(db, SUBJECT)["outcomes"] == {"incorrect": 1}


@pytest.mark.parametrize("black", [False, True])
def test_promotion_requires_accepted_history_and_verified_local_resources(monkeypatch, black):
    from chess_coach import objective_pawn_proof as module

    board = chess.Board("7k/P1K5/8/8/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    board.push_uci("a2a1q" if black else "a7a8q")
    assert module.supported(board)
    assert not module.supported(chess.Board(board.fen()))
    monkeypatch.setattr(pawn_proof, "open_verified", lambda: None)
    assert module.inspect(board, node_limit=12)["reason"] == "proof_resources_unavailable"

    class Table:
        closed = False

        def close(self):
            self.closed = True

    table = Table()
    seen = []
    monkeypatch.setattr(pawn_proof, "open_verified", lambda: table)
    monkeypatch.setattr(
        module,
        "report",
        lambda actual, tb, nodes, depth: (
            seen.append((actual.fen(), [move.uci() for move in actual.move_stack], nodes, depth))
            or {"status": "unknown", "reason": "table_missing"}
        ),
    )
    with pytest.raises(ValueError):
        module.inspect(board, node_limit=0)
    with pytest.raises(ValueError):
        module.inspect(board, node_limit=pawn_proof.MAX_NODES + 1)
    result = module.inspect(board, node_limit=12)
    assert result["status"] == "unknown" and table.closed
    assert seen[0][0] == board.fen() and seen[0][1][-1].endswith("q") and seen[0][2] == 12


@pytest.mark.parametrize("black", [False, True])
def test_promotion_does_not_itself_prove_a_win(monkeypatch, black):
    from chess_coach import objective_pawn_judge as module

    board = chess.Board("7k/P1K5/8/8/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    move = board.parse_uci("a2a1n" if black else "a7a8n")
    report = {
        "status": "complete",
        "lower": 1,
        "upper": 1,
        "nodes": 1,
        "alternatives": [{"move": {"uci": move.uci()}, "lower": 0, "upper": 0}],
    }
    monkeypatch.setattr(module, "inspect", lambda board, **kw: report)
    result = judge(board, move, 1, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["status"] == "incorrect" and result["upper"] == 0


def test_timeout_and_shared_node_budget(monkeypatch):
    from chess_coach import objective_pawn_judge as root_module
    from chess_coach import objective_pawn_reply as reply_module

    board = chess.Board(FEN)
    move = board.parse_uci("e3f3")
    calls = []
    root = synthetic_proof(board)
    root["nodes"] = 2500
    monkeypatch.setattr(
        root_module, "inspect", lambda position, *, node_limit: calls.append(node_limit) or root
    )

    def child(position, *, node_limit):
        calls.append(node_limit)
        return {"status": "unknown", "alternatives": []}

    monkeypatch.setattr(reply_module, "inspect", child)
    result = judge(board, move, 1, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["status"] == "correct" and result["continuation"]["status"] == "unavailable"
    assert calls == [3000, 3500]
    ticks = iter((0.0, 10.0))
    assert judge(board, move, 1, lambda: next(ticks), 0.0, 5.0, {}, data())["reason"] == "timeout"
    invalid = data() | {"proof_manifest_sha256": "changed"}
    assert (
        judge(board, move, 1, lambda: 0.0, 0.0, 5.0, {}, invalid)["reason"]
        == "proof_version_changed"
    )


def test_verified_table_manifest_and_content_tampering(tmp_path, monkeypatch):
    import hashlib
    import json

    assert pawn_tables.open_verified(tmp_path) is None
    content = bytes(range(80))
    table_file = tmp_path / "KQvK.rtbw"
    table_file.write_bytes(content)
    manifest = {
        "KQvK.rtbw": {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "embedded": content[-16:].hex(),
        }
    }
    raw = json.dumps(manifest).encode()
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_bytes(raw)
    monkeypatch.setattr(pawn_tables, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())

    class Table:
        def __init__(self, max_fds):
            self.files = []

        def add_file(self, path):
            self.files.append(path)

    monkeypatch.setattr(chess.syzygy, "Tablebase", Table)
    assert pawn_tables.open_verified(tmp_path).files == [str(table_file)]
    table_file.write_bytes(b"X" + content[1:])
    assert pawn_tables.open_verified(tmp_path) is None
    table_file.write_bytes(content)
    manifest_file.write_bytes(raw + b" ")
    assert pawn_tables.open_verified(tmp_path) is None


def test_correct_result_does_not_invent_an_unavailable_continuation(tmp_path, monkeypatch):
    from chess_coach import objective_pawn_reply

    db, evidence = setup_game(tmp_path / "unavailable.sqlite", monkeypatch)
    monkeypatch.setattr(objective_pawn_reply, "inspect", lambda board, **kw: {"status": "unknown"})
    begin(db, evidence, "one")
    submit(db, "one", SUBJECT, event_id="move", move="e3f3")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    state = show(db, "one", SUBJECT)
    assert state["status"] == "needs_verification" and state["pawn_continuation_unavailable"]
    assert state["verification"]["status"] == "correct"


def test_review_revocation_before_publication_cancels_pawn_verdict(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence
    from chess_coach.objective_verify import compute

    db, evidence = setup_game(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence, "race")
    submit(db, "race", SUBJECT, event_id="move", move="e3f3")

    def revoke(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(database, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, SUBJECT, verifier=revoke)["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["reason"] == "source_unavailable" and result["learning_eligible"] is False


def test_a_proved_win_preserves_a_draw_goal(monkeypatch):
    from chess_coach import objective_pawn_judge as module
    from chess_coach import objective_pawn_reply

    monkeypatch.setattr(objective_pawn_reply, "inspect", lambda board, **kw: {"status": "unknown"})
    board = chess.Board(FEN)
    move = board.parse_uci("e3f3")
    proof = synthetic_proof(board)
    monkeypatch.setattr(module, "inspect", lambda board, **kw: proof)
    result = judge(board, move, 0, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["status"] == "correct" and result["goal"] == 0


def test_browser_and_cli_resume_multiple_checked_turns(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_unified_practice import handle_show, handle_start
    from chess_coach.db import Database
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "browser.sqlite"
    db, evidence = setup_game(path, monkeypatch)
    monkeypatch.setattr("chess_coach.pawn_practice_preview.resources_available", lambda: True)
    handle_start(
        db,
        Namespace(
            attempt="cli", subject=SUBJECT, source="own-game", version=VERSION, key=str(evidence)
        ),
    )
    assert json.loads(capsys.readouterr().out)["objective"] == "preserve_pawn_win"
    handle_show(db, Namespace(attempt="cli", subject=SUBJECT))
    assert json.loads(capsys.readouterr().out)["status"] == "active"
    db.close()
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200 and b"Verify pawn result objective" in library.data
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": VERSION,
            "key": str(evidence),
        },
    )
    assert response.status_code == 303
    page = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    attempt = token(page, "attempt")
    first = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "attempt": attempt,
            "event": token(page, "event"),
            "move": "e3f3",
        },
    )
    assert first.status_code == 303
    db = Database(path)
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    state = show(db, attempt, SUBJECT)
    second_move = next(iter(chess.Board(state["fen"]).legal_moves)).uci()
    db.close()
    resumed = client.get(
        first.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert (
        b"legal training reply" in resumed.data
        and b"not presented as best or forced" in resumed.data
    )
    second = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(resumed, "csrf"),
            "attempt": attempt,
            "event": token(resumed, "event"),
            "move": second_move,
        },
    )
    assert second.status_code == 303
    pending = client.get(
        second.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert pending.status_code == 200 and b"Verification is queued" in pending.data
    db = Database(path)
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert show(db, attempt, SUBJECT)["pawn_continuation"]
    db.close()


@pytest.mark.parametrize("black", [False, True])
def test_verified_local_tables_cover_synthetic_promotion_descendants(black):
    from chess_coach.objective_pawn_proof import inspect as inspect_descendant

    source = chess.Board("7k/P1K5/8/8/8/8/8/8 w - - 0 1")
    if black:
        source = source.mirror()
    queen = source.copy(stack=True)
    knight = source.copy(stack=True)
    queen.push_uci("a2a1q" if black else "a7a8q")
    knight.push_uci("a2a1n" if black else "a7a8n")
    queen_result = inspect_descendant(queen, node_limit=30)
    knight_result = inspect_descendant(knight, node_limit=30)
    assert (queen_result["lower"], queen_result["upper"]) == (-1, -1)
    assert (knight_result["lower"], knight_result["upper"]) == (0, 0)


@pytest.mark.parametrize("black", [False, True])
def test_verified_local_promotion_intervals_grade_the_announced_goal(monkeypatch, black):
    from chess_coach import objective_pawn_judge as root_module
    from chess_coach import objective_pawn_reply as reply_module

    board = chess.Board("7k/P1K5/8/8/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    proof = pawn_proof.inspect(board, node_limit=100, max_plies=2)
    monkeypatch.setattr(root_module, "inspect", lambda board, **kw: proof)
    monkeypatch.setattr(reply_module, "inspect", lambda board, **kw: {"status": "unknown"})
    queen = board.parse_uci("a2a1q" if black else "a7a8q")
    knight = board.parse_uci("a2a1n" if black else "a7a8n")
    assert judge(board, queen, 1, lambda: 0.0, 0.0, 5.0, {}, data())["status"] == "correct"
    assert judge(board, knight, 1, lambda: 0.0, 0.0, 5.0, {}, data())["status"] == "incorrect"


def test_halfmove_castling_and_repetition_history_fail_closed(monkeypatch):
    board = chess.Board("8/8/8/8/2k5/4K3/3P4/8 w - - 7 1")
    result = judge(board, board.parse_uci("e3e4"), 1, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["reason"] == "pawn_history_or_scope_unavailable"
    castling = chess.Board("4k3/8/8/8/8/8/4P3/4K2R w K - 0 1")
    result = judge(castling, castling.parse_uci("e2e3"), 0, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["reason"] == "pawn_history_or_scope_unavailable"
    repeated = chess.Board("8/8/8/8/8/8/4P3/K6k w - - 0 1")
    for text in ("a1b1", "h1g1", "b1a1", "g1h1") * 2:
        repeated.push_uci(text)
    result = judge(repeated, repeated.parse_uci("e2e3"), 0, lambda: 0.0, 0.0, 5.0, {}, data())
    assert result["reason"] == "terminal_or_illegal_move"


def test_verified_local_en_passant_result_preserves_original_state(monkeypatch):
    from chess_coach import objective_pawn_judge as root_module
    from chess_coach import objective_pawn_reply as reply_module

    board = chess.Board("8/8/8/3pP3/8/8/8/4K2k w - d6 0 1")
    proof = pawn_proof.inspect(board, node_limit=50, max_plies=2)
    assert proof["lower"] == proof["upper"] == 1
    monkeypatch.setattr(root_module, "inspect", lambda actual, **kw: proof)
    monkeypatch.setattr(reply_module, "inspect", lambda actual, **kw: {"status": "unknown"})
    result = judge(board, board.parse_uci("e5d6"), 1, lambda: 0.0, 0.0, 5.0, {}, data())
    assert (
        result["status"] == "correct" and board.ep_square == chess.D6 and board.halfmove_clock == 0
    )


@pytest.mark.parametrize("black", [False, True])
def test_verified_tempo_choices_grade_proved_intervals(monkeypatch, black):
    from chess_coach import objective_pawn_judge as root_module
    from chess_coach import objective_pawn_reply as reply_module

    board = chess.Board("8/8/8/8/8/8/P3k3/K7 w - - 0 1")
    if black:
        board = board.mirror()
    proof = pawn_proof.inspect(board, node_limit=40, max_plies=1)
    assert proof["lower"] == proof["upper"] == 1
    monkeypatch.setattr(root_module, "inspect", lambda board, **kw: proof)
    monkeypatch.setattr(reply_module, "inspect", lambda board, **kw: {"status": "unknown"})
    good = board.parse_uci("a7a5" if black else "a2a4")
    bad = board.parse_uci("a7a6" if black else "a2a3")
    assert judge(board, good, 1, lambda: 0.0, 0.0, 5.0, {}, data())["status"] == "correct"
    assert judge(board, bad, 1, lambda: 0.0, 0.0, 5.0, {}, data())["status"] == "incorrect"


@pytest.mark.parametrize("black", [False, True])
def test_verified_opposition_with_overlapping_bounds_stays_unresolved(monkeypatch, black):
    from chess_coach import objective_pawn_judge as root_module

    board = chess.Board("8/8/8/3k4/8/3K4/3P4/8 w - - 0 1")
    if black:
        board = board.mirror()
    proof = pawn_proof.inspect(board, node_limit=100, max_plies=2)
    assert proof["geometry"]["direct_opposition"] and proof["lower"] == proof["upper"] == 0
    monkeypatch.setattr(root_module, "inspect", lambda board, **kw: proof)
    move = next(iter(board.legal_moves))
    assert judge(board, move, 0, lambda: 0.0, 0.0, 5.0, {}, data())["status"] == "unresolved"


def test_public_collection_version_collision_does_not_route_as_owned_pawn(tmp_path):
    from chess_coach.public_training import import_collection
    from tests.test_public_training import file_set

    source, manifest, metadata = file_set(
        tmp_path, rows=[("collision", FEN, "legal_line", ["e3e4"])]
    )
    manifest.write_text(json.dumps(metadata | {"version": VERSION}))
    db = Database(tmp_path / "collision.sqlite")
    db.initialize()
    import_collection(db, source, source, manifest, project_root=tmp_path)
    start(
        db,
        attempt_id="public",
        subject=SUBJECT,
        source_type="public",
        version=VERSION,
        key="collision",
    )
    result = submit(db, "public", SUBJECT, event_id="move", move="e3e4")
    assert result["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    assert show(db, "public", SUBJECT)["status"] == "line_completed"


def test_pawn_routing_requires_source_type_version_and_goal():
    from chess_coach.objective_pawn_contract import is_source

    row = {"source_type": "own-game", "source_version": VERSION, "objective": "preserve_pawn_win"}
    assert is_source(row)
    assert not is_source(row | {"source_type": "public"})
    assert not is_source(row | {"source_version": "other"})
    assert not is_source(row | {"objective": "promotion"})
