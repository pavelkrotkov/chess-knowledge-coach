"""Certified pin transfer workflows preserve source and admission boundaries."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.related_pin import preview
from chess_coach.related_pin_budget import create
from chess_coach.related_pin_line import candidate_line
from chess_coach.related_pin_source import source_for_evidence
from chess_coach.related_pin_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.test_objective_pin import SUBJECT, owned_pin


def _candidate(source):
    line = source["lines"][0].split()
    for file in "abcdefgh":
        board = chess.Board(source["prompt_fen"])
        board.turn = not board.turn
        rank, destination = ("2", "3") if board.turn else ("7", "6")
        origin = chess.parse_square(file + rank)
        if board.piece_at(origin):
            continue
        board.set_piece_at(origin, chess.Piece(chess.PAWN, board.turn))
        setup = file + rank + file + destination
        move = chess.Move.from_uci(setup)
        if not board.is_valid() or move not in board.legal_moves:
            continue
        after = board.copy(stack=True)
        after.push(move)
        if candidate_line(after, line, source["features"], create()):
            return board.fen(), setup + " " + " ".join(line)
    for file in "abcdefgh":
        for extra_file in "abcdefgh":
            board = chess.Board(source["prompt_fen"])
            opponent = not board.turn
            target_rank, origin_rank = ("3", "2") if opponent else ("6", "7")
            target = chess.parse_square(file + target_rank)
            origin = chess.parse_square(file + origin_rank)
            extra = chess.parse_square(extra_file + ("2" if board.turn else "7"))
            if board.piece_at(target) != chess.Piece(chess.PAWN, opponent):
                continue
            if board.piece_at(origin) or board.piece_at(extra):
                continue
            board.remove_piece_at(target)
            board.set_piece_at(origin, chess.Piece(chess.PAWN, opponent))
            board.set_piece_at(extra, chess.Piece(chess.PAWN, board.turn))
            board.turn = opponent
            setup = file + origin_rank + file + target_rank
            move = chess.Move.from_uci(setup)
            if not board.is_valid() or move not in board.legal_moves:
                continue
            after = board.copy(stack=True)
            after.push(move)
            if candidate_line(after, line, source["features"], create()):
                return board.fen(), setup + " " + " ".join(line)
    raise AssertionError("no synthetic candidate")


def fixture(path, monkeypatch, *, black=False, relative=False, public_only=False):
    db, evidence = owned_pin(path, monkeypatch, black=black, relative=relative)
    source = source_for_evidence(db, SUBJECT, evidence)
    fen, line = _candidate(source)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    if not public_only:
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES('fixture-pin',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (corpus, fen, line),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'pin',1200)", (corpus, "fixture-pin")
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    return db, evidence, fen, line


@pytest.mark.parametrize("black", [False, True])
def test_owned_pin_transfer_playable_concealed_and_review_bound(tmp_path, monkeypatch, black):
    relative = False
    db, evidence, _, _ = fixture(
        tmp_path / "pin.sqlite", monkeypatch, black=black, relative=relative
    )
    result = preview(db, SUBJECT, evidence, "test")
    assert result["status"] == "available" and len(result["items"]) == 1
    source = source_for_evidence(db, SUBJECT, evidence)
    visible = {
        **result,
        "items": [{k: v for k, v in item.items() if k != "reference"} for item in result["items"]],
    }
    visible.pop("scope", None)
    assert source["lines"][0].split()[0] not in json.dumps(visible)
    assert "candidate_certificates" not in json.dumps(result)
    reference = result["items"][0]["reference"]
    state = start_related(
        db,
        attempt_id="pin-transfer",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=reference,
    )
    assert state["status"] == "active" and state["objective"] == "legal_line"
    assert "source_key" not in state
    row = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id='pin-transfer'"
    ).fetchone()
    lines = json.loads(row["lines_json"])
    binding = json.loads(row["provenance_json"])["related_pin"]
    assert binding["operation"] == "execute" and binding["pattern_cued"]
    assert binding["candidate_certificates"][0]["proof"]["type"] == (
        "relative_pin" if relative else "absolute_pin"
    )
    assert len(lines[0]) == 3
    first = submit(db, "pin-transfer", SUBJECT, event_id="first", move=lines[0][0])
    assert first["status"] == "active" and first["opponent_move"] == lines[0][1]
    last = submit(db, "pin-transfer", SUBJECT, event_id="last", move=lines[0][2])
    assert last["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError, match="stale"):
        show(db, "pin-transfer", SUBJECT)


def test_public_lines_filter_wrong_operation_and_keep_only_certified_branch(tmp_path, monkeypatch):
    from chess_coach.related_pin_match import scorer

    db, evidence, fen, full = fixture(tmp_path / "public.sqlite", monkeypatch, public_only=True)
    source = source_for_evidence(db, SUBJECT, evidence)
    board = chess.Board(fen)
    words = full.split()
    board.push_uci(words[0])
    good = " ".join(words[1:])
    creation = board.parse_uci(words[1])
    board.push(creation)
    defense = board.parse_uci(words[2])
    board.push(defense)
    alternate = next(move.uci() for move in board.legal_moves if move.uci() != words[3])
    bad = " ".join((words[1], words[2], alternate))
    prompt = chess.Board(fen)
    prompt.push_uci(words[0])
    wrong = {"type": "public", "objective": "promotion", "fen": prompt.fen(), "lines": [good]}
    assert scorer(create())(wrong, source["features"], set(), None) is None
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES('public-v1','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
    collection = db.connection.execute(
        "SELECT id FROM public_collections WHERE version='public-v1'"
    ).fetchone()[0]
    db.connection.execute(
        "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
        (collection, "public-pin", prompt.fen(), "legal_line", json.dumps([bad, good])),
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=?", (collection,))
    db.connection.commit()
    result = preview(db, SUBJECT, evidence, "test")
    assert len(result["items"]) == 1 and result["items"][0]["type"] == "public"
    state = start_related(
        db,
        attempt_id="public",
        subject=SUBJECT,
        evidence_id=evidence,
        corpus_version="test",
        reference=result["items"][0]["reference"],
    )
    assert state["objective"] == "legal_line"
    saved = json.loads(
        db.connection.execute(
            "SELECT lines_json FROM unified_sessions WHERE attempt_id='public'"
        ).fetchone()[0]
    )
    assert saved == [good.split()]


def test_cli_and_private_browser_preview_csrf_and_start(tmp_path, monkeypatch, capsys):
    import sys

    from chess_coach.cli import main
    from chess_coach.web import create_app

    path = tmp_path / "clients.sqlite"
    db, evidence, _, _ = fixture(path, monkeypatch)
    chosen = preview(db, SUBJECT, evidence, "test")
    reference = chosen["items"][0]["reference"]
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "related-pins",
            "--subject",
            SUBJECT,
            "--evidence",
            str(evidence),
            "--corpus",
            "test",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["items"][0]["reference"] == reference
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "start-related-pin",
            "--subject",
            SUBJECT,
            "--evidence",
            str(evidence),
            "--corpus",
            "test",
            "--attempt",
            "cli",
            "--reference",
            reference,
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["objective"] == "legal_line"
    path = tmp_path / "browser.sqlite"
    db, evidence, _, _ = fixture(path, monkeypatch)
    reference = preview(db, SUBJECT, evidence, "test")["items"][0]["reference"]
    db.close()
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert source.status_code == 200 and b"Find related pin practice" in source.data
    page = client.get(
        f"/evidence/{evidence}/related-pins", base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"Practice this pin pattern" in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    url = f"/evidence/{evidence}/related-pins/start"
    data = {"csrf": csrf, "reference": reference}
    assert (
        client.post(url, base_url="https://coach.invalid", headers=headers, data=data).status_code
        == 403
    )
    response = client.post(
        url,
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=data,
    )
    assert response.status_code == 303
    assert (
        client.get(
            response.headers["Location"], base_url="https://coach.invalid", headers=headers
        ).status_code
        == 200
    )


def _long_candidate(source):
    import random

    for branch in source["provenance"]["pin_certificate"]["branches"]:
        if branch["mate"]:
            continue
        sample = dict(source)
        creation = source["provenance"]["pin_certificate"]["move"]
        sample["lines"] = [" ".join((creation, branch["reply"], branch["capture"]))]
        fen, initial = _candidate(sample)
        for seed in range(20):
            rng = random.Random(seed)
            board = chess.Board(fen)
            words = initial.split()
            for move in words:
                board.push_uci(move)
            while len(words) < 66:
                choices = list(board.legal_moves)
                rng.shuffle(choices)
                for move in choices:
                    board.push(move)
                    if not board.is_game_over(claim_draw=True):
                        words.append(move.uci())
                        break
                    board.pop()
                else:
                    break
            if len(words) == 66:
                return fen, words
    raise AssertionError("no long synthetic pin witness")


def _check_source_length(tmp_path, monkeypatch, source_kind, length, accepted):
    from chess_coach import related_pin_certificate
    from chess_coach.unified_sources import resolve_source

    db, evidence = owned_pin(tmp_path / "boundary.sqlite", monkeypatch, relative=True)
    source = source_for_evidence(db, SUBJECT, evidence)
    fen, full = _long_candidate(source)
    board = chess.Board(fen)
    board.push_uci(full[0])
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='test'").fetchone()[
        0
    ]
    if source_kind == "corpus":
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES('boundary',?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (corpus, fen, " ".join(full[:length])),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'pin',1200)", (corpus, "boundary")
        )
        version, key = "test", "boundary"
    else:
        db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
            content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
            VALUES('public-boundary','https://example.invalid','v1','a','b','fen_csv','CC0-1.0','fixture','notice',1,0,'staging')""")
        collection = db.connection.execute(
            "SELECT id FROM public_collections WHERE version='public-boundary'"
        ).fetchone()[0]
        db.connection.execute(
            "INSERT INTO public_tasks VALUES(?,?,?,?,?)",
            (
                collection,
                "boundary",
                board.fen(),
                "legal_line",
                json.dumps([" ".join(full[1 : length + 1])]),
            ),
        )
        db.connection.execute(
            "UPDATE public_collections SET state='ready' WHERE id=?", (collection,)
        )
        version, key = "public-boundary", "boundary"
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    if not accepted:
        monkeypatch.setattr(
            related_pin_certificate, "proven", lambda *_: pytest.fail("oversize proof")
        )
    result = preview(db, SUBJECT, evidence, "test")
    if accepted:
        assert len(result["items"]) == 1
        state = start_related(
            db,
            attempt_id="boundary",
            subject=SUBJECT,
            evidence_id=evidence,
            corpus_version="test",
            reference=result["items"][0]["reference"],
        )
        assert state["status"] == "active"
    else:
        assert result["items"] == [] and result["pin_scan"]["root_proofs"] == 0
        with pytest.raises(ValueError):
            resolve_source(db, source_kind, version, key, subject=SUBJECT)
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="boundary",
                subject=SUBJECT,
                evidence_id=evidence,
                corpus_version="test",
                reference="stale-reference",
            )


def test_transfer_source_length_bound_matches_session_admission(tmp_path, monkeypatch):
    for kind, length, accepted in (
        ("corpus", 64, True),
        ("corpus", 66, False),
        ("public", 64, True),
        ("public", 65, False),
    ):
        case = tmp_path / f"{kind}-{length}"
        case.mkdir()
        with monkeypatch.context() as scoped:
            _check_source_length(case, scoped, kind, length, accepted)
