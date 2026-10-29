"""One-move defense outcomes use complete legal replies and owned history."""

import json

import chess
import pytest

from chess_coach.back_rank_auto import process_decision as process_back_rank
from chess_coach.evidence_review import review_evidence
from chess_coach.mate_auto import process_decision as process_mate
from chess_coach.objective_defense_judge import judge
from chess_coach.objective_defense_source import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import hint, reveal, show, submit
from chess_coach.unified_sessions import start
from tests.test_back_rank import DEFENSE
from tests.test_mate_proof import owned_game


def fixture(path, monkeypatch, black=False, fen=None, move=None):
    subject = "fixture_b" if black else "fixture_a"
    board = chess.Board(fen or DEFENSE)
    if black:
        board = board.mirror()
    db = owned_game(path, monkeypatch, fen=board.fen(), move=move or ("g6" if black else "g3"))
    process_mate(db, 1, subject)
    process_back_rank(db, 1, subject)
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?", ("back_rank", "prevent")
    ).fetchone()[0]
    return db, evidence, subject


def begin(db, evidence, subject, attempt="attempt"):
    return start(
        db,
        attempt_id=attempt,
        subject=subject,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def choices(db, attempt):
    row = db.connection.execute(
        "SELECT prompt_fen,lines_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()
    board = chess.Board(row["prompt_fen"])
    exemplar = json.loads(row["lines_json"])[0][0]
    safe, unsafe = [], []
    for move in board.legal_moves:
        result = judge(board, move, lambda: 0.0, 0.0, 5.0, {})
        if move.uci() != exemplar and result["status"] == "correct":
            safe.append(move.uci())
        if result["status"] == "incorrect":
            unsafe.append(move.uci())
    return exemplar, safe[0], unsafe[0]


@pytest.mark.parametrize("black", [False, True])
def test_owned_alternative_and_refutation_are_durable_and_distinct(tmp_path, monkeypatch, black):
    db, evidence, subject = fixture(tmp_path / "defense.sqlite", monkeypatch, black)
    tracked = (
        "evidence_mappings",
        "evidence_review_events",
        "mastery_states",
        "mastery_events",
        "training_items",
        "training_attempts",
        "training_completions",
    )
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    }
    begin(db, evidence, subject)
    exemplar, safe, unsafe = choices(db, "attempt")
    assert submit(db, "attempt", subject, event_id="null", move="0000")["feedback"] == "illegal"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    assert hint(db, "attempt", subject, event_id="hint")["assistance_kind"] == "hinted"
    assert reveal(db, "attempt", subject, event_id="reveal")["assistance_kind"] == "revealed"
    with pytest.raises(ValueError):
        reveal(db, "attempt", subject, event_id="hint")
    original = submit(db, "attempt", subject, event_id="move", move=safe)
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("move",)
    ).fetchone()[0]
    assert process(db, subject)["outcomes"] == {"correct": 1}
    result = inspect(db, subject, "attempt", "move")
    assert result["reason"] == "no_immediate_checkmate_reply" and result["assistance"] == "revealed"
    assert submit(db, "attempt", subject, event_id="move", move=safe) == original
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("move",)
        ).fetchone()[0]
        == frozen
    )
    changes = db.connection.total_changes
    assert show(db, "attempt", subject)["verification"]["status"] == "correct"
    assert db.connection.total_changes == changes
    assert process(db, subject)["processed"] == 0
    begin(db, evidence, subject, "unsafe")
    submit(db, "unsafe", subject, event_id="move", move=unsafe)
    assert process(db, subject)["outcomes"] == {"incorrect": 1}
    assert inspect(db, subject, "unsafe", "move")["reason"] == "opponent_immediate_checkmate"
    result = json.loads(
        db.connection.execute(
            "SELECT result_json FROM objective_results WHERE attempt_id=?", ("unsafe",)
        ).fetchone()[0]
    )
    assert result["mate_reply"] and result["learning_eligible"] is False
    board = chess.Board(
        db.connection.execute(
            "SELECT prompt_fen FROM unified_sessions WHERE attempt_id=?", ("unsafe",)
        ).fetchone()[0]
    )
    board.push_uci(unsafe)
    assert set(result["legal_replies"]) == {move.uci() for move in board.legal_moves}
    assert result["replies_scanned"] == len(result["legal_replies"])
    begin(db, evidence, subject, "example")
    assert (
        submit(db, "example", subject, event_id="move", move=exemplar)["status"]
        == "objective_verified"
    )
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    } == before


def test_non_back_rank_reply_refutes_the_exact_objective():
    board = chess.Board("r5k1/q7/8/8/1N5b/8/5PPP/6K1 w - - 0 1")
    result = judge(board, board.parse_uci("g1f1"), lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "incorrect" and result["mate_reply"]["uci"] == "a7f2"
    board.push_uci("g1f1")
    board.push_uci(result["mate_reply"]["uci"])
    assert board.is_checkmate()


def test_timeout_incomplete_and_terminal_are_never_false_success(monkeypatch):
    import chess_coach.objective_defense_scan as module

    board = chess.Board(DEFENSE)
    move = board.parse_uci("g2g3")
    ticks = iter([10.0] * 1000)
    assert judge(board, move, lambda: next(ticks), 0.0, 5.0, {})["reason"] == "timeout"
    monkeypatch.setattr(module, "MAX_NODES", 1)
    limited = judge(board, move, lambda: 0.0, 0.0, 5.0, {})
    assert limited["status"] == "unresolved" and limited["reason"] == "node_limit"
    stalemate = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
    result = judge(stalemate, stalemate.parse_uci("g6f7"), lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "unresolved" and result["reason"] == "terminal_position"


def test_postcompute_revoke_cannot_publish_a_defense_claim(tmp_path, monkeypatch):
    from chess_coach.objective_verify import compute

    db, evidence, subject = fixture(tmp_path / "revoked.sqlite", monkeypatch)
    begin(db, evidence, subject)
    _, safe, _ = choices(db, "attempt")
    submit(db, "attempt", subject, event_id="move", move=safe)

    def verifier(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(database, evidence, decision="reject", actor="reviewer")
        return result

    assert process(db, subject, verifier=verifier)["outcomes"] == {"unresolved": 1}
    assert (
        json.loads(
            db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
        )["reason"]
        == "source_unavailable"
    )
    with pytest.raises(ValueError):
        show(db, "attempt", subject)


@pytest.mark.parametrize(
    "field,value",
    [
        ("producer", "foreign"),
        ("mapper_version", "foreign"),
        ("subject", "fixture_other"),
        ("operation", "execute"),
        ("position_id", -1),
        ("scope_key", "foreign"),
        ("status", "superseded"),
    ],
)
def test_linked_run_identity_change_invalidates_source_and_queued_result(
    tmp_path, monkeypatch, field, value
):
    db, evidence, subject = fixture(tmp_path / "identity.sqlite", monkeypatch)
    begin(db, evidence, subject)
    _, safe, _ = choices(db, "attempt")
    submit(db, "attempt", subject, event_id="move", move=safe)
    run_id = db.connection.execute(
        "SELECT mapping_run_id FROM evidence_mappings WHERE id=?", (evidence,)
    ).fetchone()[0]
    if field == "position_id":
        from chess_coach.ingest import ingest_pgn

        pgn = """[Event "Another synthetic game"]
[White "fixture_a"]
[Black "fixture_b"]
[SetUp "1"]
[FEN "r5k1/8/8/8/2N5/8/5PPP/6K1 w - - 0 1"]
[Result "*"]

1. g3 Ra1+ *
"""
        ingest_pgn(db, pgn)
        value = db.connection.execute("SELECT MAX(id) FROM positions").fetchone()[0]
    db.connection.execute(f"UPDATE mapping_runs SET {field}=? WHERE id=?", (value, run_id))
    db.connection.commit()
    assert process(db, subject)["outcomes"] == {"unresolved": 1}
    assert (
        json.loads(
            db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
        )["reason"]
        == "source_unavailable"
    )
    with pytest.raises(ValueError):
        show(db, "attempt", subject)


def test_claimable_repetition_and_null_move_are_unresolved():
    repeated = chess.Board()
    for text in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        repeated.push_uci(text)
    assert repeated.can_claim_threefold_repetition()
    assert (
        judge(repeated, repeated.parse_uci("g1f3"), lambda: 0.0, 0.0, 5.0, {})["reason"]
        == "terminal_or_claimable_history"
    )
    board = chess.Board(DEFENSE)
    assert judge(board, chess.Move.null(), lambda: 0.0, 0.0, 5.0, {})["reason"] == "illegal_move"


@pytest.mark.parametrize("fen", [DEFENSE, "r5k1/q7/8/8/1N5b/8/5PPP/6K1 w - - 0 1"])
@pytest.mark.parametrize("black", [False, True])
def test_legal_alternatives_match_independent_checkmate_enumeration(fen, black):
    board = chess.Board(fen)
    if black:
        board = board.mirror()
    original = board.fen()
    for move in list(board.legal_moves):
        result = judge(board, move, lambda: 0.0, 0.0, 5.0, {})
        child = board.copy(stack=True)
        child.push(move)
        if child.is_checkmate():
            expected = "correct"
        elif child.outcome(claim_draw=False):
            expected = "unresolved"
        else:
            replies = []
            for reply in child.legal_moves:
                child.push(reply)
                replies.append(child.is_checkmate())
                child.pop()
            expected = (
                "incorrect"
                if any(replies)
                else "unresolved"
                if child.can_claim_draw()
                else "correct"
            )
        assert result["status"] == expected
        assert board.fen() == original


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize(
    "fen,text,checkers,countercheck",
    [
        ("k7/8/8/8/8/8/6rQ/6K1 w - - 0 1", "h2g2", 1, True),
        ("k7/8/8/8/8/8/6rb/1R4K1 w - - 0 1", "g1g2", 2, False),
    ],
)
def test_legal_countercheck_and_double_check_escape(fen, text, checkers, countercheck, black):
    board = chess.Board(fen)
    move = chess.Move.from_uci(text)
    if black:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    assert board.is_valid() and len(board.checkers()) == checkers
    assert move in board.legal_moves and board.is_capture(move)
    assert board.gives_check(move) is countercheck
    assert judge(board, move, lambda: 0.0, 0.0, 5.0, {})["status"] == "correct"


def test_source_change_during_exemplar_verification_is_rejected(tmp_path, monkeypatch):
    from chess_coach import objective_defense_source

    db, evidence, subject = fixture(tmp_path / "source-race.sqlite", monkeypatch)
    run_id = db.connection.execute(
        "SELECT mapping_run_id FROM evidence_mappings WHERE id=?", (evidence,)
    ).fetchone()[0]
    original = objective_defense_source.choose

    def change(board, payload):
        result = original(board, payload)
        db.connection.execute(
            "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("foreign", run_id)
        )
        return result

    monkeypatch.setattr(objective_defense_source, "choose", change)
    with pytest.raises(ValueError):
        objective_defense_source.resolve(db, VERSION, str(evidence), subject)
    db.connection.rollback()


def test_actual_learner_checkmate_satisfies_defense_objective():
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    result = judge(board, board.parse_uci("f7e8"), lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "correct" and result["reason"] == "learner_checkmate"


def test_owned_history_is_bound_to_proof_and_retry_worker(tmp_path, monkeypatch, capsys):
    import sys

    import chess.engine

    from chess_coach import ops_retry, pipeline_sync
    from chess_coach.db import Database
    from chess_coach.decision_history import decision_board
    from chess_coach.ingest import ingest_pgn
    from chess_coach.mate_inspection_source import position_row
    from chess_coach.objective_short_history import history_hash
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_health import start_run
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from tests.test_mate_proof import Engine

    path = tmp_path / "history.sqlite"
    db = Database(path)
    db.initialize()
    pgn = """[Event \"Synthetic\"]
[White \"fixture_a\"]
[Black \"fixture_b\"]
[SetUp \"1\"]
[FEN \"6k1/r7/8/8/2N5/8/5PPP/6K1 b - - 0 1\"]
[Result \"*\"]

1... Ra8 2. g3 *
"""
    ingest_pgn(db, pgn)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    position = db.connection.execute("SELECT id FROM positions WHERE uci=?", ("g2g3",)).fetchone()[
        0
    ]
    board = decision_board(db, position_row(db, position))
    assert [move.uci() for move in board.move_stack] == ["a7a8"]
    process_mate(db, position, "fixture_a")
    process_back_rank(db, position, "fixture_a")
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE position_id=? AND skill=? AND operation=?",
        (position, "back_rank", "prevent"),
    ).fetchone()[0]
    begin(db, evidence, "fixture_a")
    _, safe, _ = choices(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=safe)
    start_run(db)
    db.connection.execute(
        "UPDATE pipeline_health SET retry_until=? WHERE id=1", ("2099-01-01T00:00:00+00:00",)
    )
    db.connection.commit()
    before = tuple(db.connection.execute("SELECT * FROM pipeline_health WHERE id=1").fetchone())
    db.close()
    calls = []
    monkeypatch.setenv("LICHESS_USERNAME", "fixture_a")
    monkeypatch.setattr(ops_retry, "database_path", lambda: path)
    monkeypatch.setattr(pipeline_sync, "sync_games", lambda *args, **kwargs: calls.append(True))
    ops_retry.main()
    assert not calls and capsys.readouterr().out == ""
    db = Database(path)
    assert (
        tuple(db.connection.execute("SELECT * FROM pipeline_health WHERE id=1").fetchone())
        == before
    )
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["status"] == "correct" and result["history_hash"] == history_hash(board)


def test_supplied_exemplar_page_describes_defense_not_winning(tmp_path, monkeypatch):
    from chess_coach.web import create_app

    path = tmp_path / "exemplar.sqlite"
    db, evidence, subject = fixture(path, monkeypatch)
    begin(db, evidence, subject)
    exemplar, _, _ = choices(db, "attempt")
    assert (
        submit(db, "attempt", subject, event_id="move", move=exemplar)["status"]
        == "objective_verified"
    )
    app = create_app(
        db_path=path,
        subject=subject,
        actor="fixture",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/unified/attempt",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200 and b"Defense verified" in page.data
    assert b"does not establish overall safety or a win" in page.data
