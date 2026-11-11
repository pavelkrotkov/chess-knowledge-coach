"""Exercise private publishing and recovery with synthetic positions only."""

import io
import json

import chess
import chess.pgn
import httpx
import pytest

from chess_coach.course_gamebook import capture
from chess_coach.course_gamebook import mate as is_mate
from chess_coach.course_pgn import chapter
from chess_coach.course_preview import preview_hash
from chess_coach.study_inventory import named
from chess_coach.study_pgn_verify import matches
from chess_coach.study_publisher import publish
from chess_coach.study_remote import SETTINGS, Remote, StudyError
from chess_coach.web_study_status import status


class Provider:
    def __init__(self):
        self.name = None
        self.created = 0
        self.uploaded = []
        self.private = True
        self.owner = "learner"
        self.settings = dict(SETTINGS)
        self.timeout_create = True
        self.timeout_upload = True
        self.upload_status = None
        self.upload_error = False
        self.force_mode = None
        self.change_name_on_export = False
        self.anonymous_status = 401
        self.inventory_count = 1
        self.create_status = None
        self.empty_id = "empty000"
        self.scopes = "study:read,study:write"

    def request(self, method, url, **kwargs):
        assert kwargs["headers"]["User-Agent"] == "Mozilla/5.0 (compatible; ChessCoach/1.0)"
        path = httpx.URL(url).path
        request = httpx.Request(method, url)
        if path == "/api/account":
            return httpx.Response(
                200, json={"id": "learner", "username": "learner"}, request=request
            )
        if path == "/api/token/test":
            return httpx.Response(
                200, json={"fixture-token": {"scopes": self.scopes}}, request=request
            )
        if path == "/api/study/by/learner":
            rows = (
                [{"id": "abcd1234", "name": self.name}] * self.inventory_count if self.name else []
            )
            return httpx.Response(200, text="\n".join(map(json.dumps, rows)), request=request)
        if path == "/api/study" and method == "POST":
            self.created += 1
            if self.create_status is not None:
                return httpx.Response(self.create_status, request=request)
            assert kwargs["data"]["visibility"] == "private"
            assert all(kwargs["data"][key] == value for key, value in SETTINGS.items())
            self.name = kwargs["data"]["name"]
            if self.timeout_create:
                self.timeout_create = False
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(200, json={"id": "abcd1234"}, request=request)
        if path.startswith("/study/abcd1234"):
            chapters = [{"id": self.empty_id, "name": "Empty"}]
            chapters.extend(
                {"id": f"ch{i:06d}", "name": item["name"]} for i, item in enumerate(self.uploaded)
            )
            value = {
                "study": {
                    "id": "abcd1234",
                    "name": self.name,
                    "ownerId": self.owner,
                    "visibility": "private" if self.private else "public",
                    "settings": self.settings,
                    "chapters": chapters,
                }
            }
            if path != "/study/abcd1234":
                chapter_id = path.rsplit("/", 1)[-1]
                item = self.uploaded[int(chapter_id[2:])]
                gamebook = item["mode"] == "gamebook"
                value["study"]["chapter"] = {
                    "id": chapter_id,
                    "conceal": None if gamebook else 0,
                    "gamebook": gamebook,
                }
            return httpx.Response(200, json=value, request=request)
        if path == "/api/study/abcd1234.pgn":
            if self.change_name_on_export:
                self.change_name_on_export = False
                self.name = "changed marker"
            return httpx.Response(200, text=self.export(), request=request)
        if path == "/api/study/abcd1234/import-pgn":
            if self.upload_status is not None:
                return httpx.Response(self.upload_status, request=request)
            item = dict(kwargs["data"])
            if self.force_mode is not None:
                item["mode"] = self.force_mode
            self.uploaded.append(item)
            if self.upload_error:
                self.upload_error = False
                return httpx.Response(
                    200, json={"chapters": [{"id": "new"}], "error": "partial"}, request=request
                )
            if self.timeout_upload:
                self.timeout_upload = False
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(200, json={"chapters": [{"id": "new"}]}, request=request)
        raise AssertionError(path)

    def anonymous(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(self.anonymous_status, request=request)

    def export(self):
        games = []
        for item in self.uploaded:
            game = chess.pgn.read_game(io.StringIO(item["pgn"]))
            assert game is not None
            if game.end().board().is_checkmate():
                winner = "0-1 Black" if game.end().board().turn else "1-0 White"
                game.end().comment = (
                    game.end().comment + " " + winner + " wins by checkmate."
                ).strip()
            game.headers["ChapterName"] = item["name"]
            game.headers["Orientation"] = item["orientation"]
            games.append(str(game))
        return "\n\n\n".join(games)


def test_private_publication_reconciles_timeouts_and_rejects_public_destination(
    tmp_path, monkeypatch
):
    snapshot = {
        "prompt_fen": chess.STARTING_FEN,
        "learner_color": "white",
        "lines": ["e2e4 e7e5", "e2e4 c7c5"],
        "provenance": {},
    }
    chapters = [
        chapter(f"Lesson {i}", "A source and a useful question.", snapshot, {}) for i in range(5)
    ]
    board = chess.Board()
    for move in ("f3", "e5", "g4"):
        board.push_san(move)
    mate = {
        "prompt_fen": board.fen(),
        "learner_color": "black",
        "lines": ["d8h4"],
        "provenance": {},
    }
    assert is_mate(mate)
    chapters[2] = chapter("Mate", "Checkmate in one move.", mate, {}, gamebook=True)
    from chess_coach.opening_study_chapter import chapter as opening_chapter

    black_chapter, _ = opening_chapter(chapters[2], "black", mate["prompt_fen"])
    assert black_chapter["orientation"] == "black" and black_chapter["mode"] == "conceal"
    assert "Black" in black_chapter["title"] and black_chapter["pgn"] == chapters[2]["pgn"]
    with pytest.raises(ValueError, match="orientation"):
        opening_chapter(chapters[2], "white", mate["prompt_fen"])
    capture_snapshot = {
        "prompt_fen": "4k3/8/8/8/8/8/4q3/4R1K1 w - - 0 1",
        "learner_color": "white",
        "objective": "capture_named_target",
        "lines": ["e1e2"],
        "provenance": {"objective_target": "e2"},
    }
    assert capture(capture_snapshot) == "queen on e2"
    assert capture({**capture_snapshot, "lines": ["g1f2"]}) is None
    two_captures = {**capture_snapshot, "prompt_fen": "4k3/8/8/8/8/8/Q3q3/4R1K1 w - - 0 1"}
    assert capture(two_captures) is None
    assert chapters[0]["title"] == "Example White: Lesson 0"
    assert chapters[2]["title"] == "Play Black (Preview): Mate"
    with pytest.raises(StudyError, match="provider limit"):
        named({"title": "x" * 100}, {"marker": "a" * 16}, 0)
    assert "Worked example, ungraded. You follow White" in chapters[0]["pgn"]
    assert "Worked example, ungraded" in chapters[0]["pgn"]
    assert "You play Black" in chapters[2]["pgn"]
    assert "Interactive exercise. You play Black." in chapters[2]["pgn"]
    assert "Select Preview below the board." in chapters[2]["pgn"]
    assert "Your move is checked automatically." in chapters[2]["pgn"]
    guide = chess.pgn.read_game(io.StringIO(chapters[2]["pgn"]))
    assert guide is not None
    assert "when available, Next chapter" in guide.comment
    assert "or Lichess's checkmate result" in guide.comment
    assert "Good move" not in chapters[2]["pgn"]
    assert "Correct. Exercise complete." in chapters[2]["pgn"]
    body = {"preview_sha256": "fixture", "chapters": chapters}
    course = {"course": body, "course_sha256": preview_hash(body)}
    provider = Provider()
    remote = Remote("fixture-token", "learner", provider)
    intent = tmp_path / "intent.json"

    provider.scopes = "study:read"
    with pytest.raises(StudyError, match="scopes"):
        publish(remote, intent, course)
    assert not provider.created and not provider.uploaded
    provider.scopes = "study:read,study:write"
    with pytest.raises(StudyError, match="unknown"):
        publish(remote, intent, course)
    assert provider.created == 1 and not provider.uploaded
    provider.private = False
    with pytest.raises(StudyError, match="privacy"):
        publish(remote, intent, course)
    assert not provider.uploaded
    provider.private = True
    with pytest.raises(StudyError, match="unknown"):
        publish(remote, intent, course)
    assert len(provider.uploaded) == 1
    link = publish(remote, intent, course)
    assert link.endswith("/abcd1234/ch000000#0")
    assert [item["mode"] for item in provider.uploaded] == [
        "conceal",
        "conceal",
        "gamebook",
        "conceal",
        "conceal",
    ]
    assert provider.created == 1 and len(provider.uploaded) == 5
    expected = {**chapters[2], "name": provider.uploaded[2]["name"]}
    assert matches(expected, provider.export())
    assert not matches(
        expected, provider.export().replace("0-1 Black wins by checkmate.", "Unrelated annotation.")
    )
    assert not matches(
        expected,
        provider.export().replace("0-1 Black wins by checkmate.", "1-0 White wins by checkmate."),
    )
    with_teaching = chess.pgn.read_game(io.StringIO(expected["pgn"]))
    assert with_teaching is not None
    with_teaching.end().comment = "Keep this teaching comment."
    assert not matches({**expected, "pgn": str(with_teaching)}, provider.export())
    assert json.loads(intent.read_text())["complete"] is True
    assert json.loads(intent.read_text())["verified_at"]
    planning = tmp_path / ".runtime" / "planning"
    planning.mkdir(parents=True)
    (planning / "poc-study-336-intent.json").write_text(intent.read_text())
    assert status(tmp_path)["url"] == link
    receipt = {
        "study": "abcd1234",
        "entry_chapter": "ch000002",
        "verified": True,
        "verified_at": "2026-01-01T00:00:00Z",
    }
    (planning / "poc-study-346-presentation.json").write_text(json.dumps(receipt))
    assert status(tmp_path)["url"].endswith("/abcd1234/ch000002#0")
    assert publish(remote, intent, course) == link
    assert provider.created == 1 and len(provider.uploaded) == 5
    provider.uploaded[2]["mode"] = "conceal"
    with pytest.raises(StudyError, match="mode"):
        publish(remote, intent, course)
    provider.uploaded[2]["mode"] = "gamebook"
    provider.name = "Unrelated study"
    with pytest.raises(StudyError, match="marker"):
        publish(remote, intent, course)
    assert len(provider.uploaded) == 5

    # Tactical imports retain ordered, source-checked chapters in a distinct private intent.
    from chess_coach.study_import_post import upload as upload_one
    from chess_coach.tactical_study_pgn import matches_mainline
    from chess_coach.tactical_study_status import status as tactical_status

    upload_planning = tmp_path / "upload-planning"
    upload_planning.mkdir(mode=0o700)
    tactical_body = {"chapters": chapters[:4], "version": "fixture"}
    tactical_course = {"course": tactical_body, "course_sha256": preview_hash(tactical_body)}
    tactical_path = (
        upload_planning / f"tactical-study-{tactical_course['course_sha256']}-intent.json"
    )
    tactical_provider = Provider()
    tactical_provider.timeout_create = False
    tactical_provider.timeout_upload = False
    tactical_remote = Remote("fixture-token", "learner", tactical_provider)
    import chess_coach.study_anonymous as anonymous

    real_client = httpx.Client
    anonymous_calls = []

    def anonymous_handler(request):
        assert "authorization" not in request.headers and "cookie" not in request.headers
        anonymous_calls.append(True)
        return httpx.Response(401, request=request)

    def anonymous_client(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return real_client(transport=httpx.MockTransport(anonymous_handler), **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(anonymous.httpx, "Client", anonymous_client)
        assert anonymous.request("https://lichess.org/api/study/abcd1234.pgn").status_code == 401
    assert anonymous_calls
    monkeypatch.setattr(anonymous, "request", tactical_provider.anonymous)
    for status_code in (401, 403, 429):
        tactical_provider.upload_status = status_code
        with pytest.raises(StudyError):
            publish(tactical_remote, tactical_path, tactical_course, strict=True)
        assert json.loads(tactical_path.read_text())["chapters"][0] == "new"
        assert not tactical_provider.uploaded
    tactical_provider.upload_status = None
    tactical_provider.timeout_upload = True
    with pytest.raises(StudyError, match="unknown"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert json.loads(tactical_path.read_text())["chapters"][0] == "pending"
    assert len(tactical_provider.uploaded) == 1
    tactical_provider.uploaded[0]["mode"] = "gamebook"
    with pytest.raises(StudyError, match="mode"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert len(tactical_provider.uploaded) == 1
    tactical_provider.uploaded[0]["mode"] = "conceal"
    tactical_provider.change_name_on_export = True
    with pytest.raises(StudyError, match="marker"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert len(tactical_provider.uploaded) == 1
    tactical_provider.name = json.loads(tactical_path.read_text())["marker"]
    tactical_provider.private = False
    with pytest.raises(StudyError, match="privacy"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert len(tactical_provider.uploaded) == 1
    tactical_provider.private = True
    tactical_provider.force_mode = "gamebook"
    with pytest.raises(StudyError, match="mode"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert json.loads(tactical_path.read_text())["chapters"][1] == "pending"
    assert len(tactical_provider.uploaded) == 2
    tactical_provider.uploaded[1]["mode"] = "conceal"
    tactical_provider.force_mode = None
    tactical_provider.upload_error = True
    with pytest.raises(StudyError, match="unresolved"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert json.loads(tactical_path.read_text())["chapters"][2] == "pending"
    assert len(tactical_provider.uploaded) == 3
    for status_code in (200, 302, 404, 429, 500):
        tactical_provider.anonymous_status = status_code
        with pytest.raises(StudyError, match="anonymous privacy"):
            publish(tactical_remote, tactical_path, tactical_course, strict=True)
        assert not json.loads(tactical_path.read_text())["complete"]
        assert len(tactical_provider.uploaded) == 4
    tactical_provider.anonymous_status = 401
    tactical_link = publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert tactical_link.endswith("/abcd1234/ch000000#0")
    verified = json.loads(tactical_path.read_text())
    assert verified["complete"] and verified["privacy_verified"] and verified["ordered_verified"]
    assert verified["anonymous_verified"]
    from chess_coach.deep_selection_source import learner_key

    assert verified["learner_key"] == learner_key("learner")
    assert verified["chapter_ids"] == ["ch000000", "ch000001", "ch000002", "ch000003"]
    assert verified["chapter_modes"] == ["conceal", "conceal", "gamebook", "conceal"]
    from chess_coach.tactical_study_order import verify as verify_tactical_order

    with pytest.raises(StudyError, match="invalid Study identifier"):
        verify_tactical_order(
            {"name": verified["marker"], "chapters": [{"id": None}]},
            {**verified, "empty_chapter": None},
            chapters[:4],
        )
    assert tactical_provider.created == 1 and len(tactical_provider.uploaded) == 4
    saved_intent = tactical_path.read_bytes()
    malformed = json.loads(saved_intent)
    malformed["chapters"] = ["done"]
    tactical_path.write_text(json.dumps(malformed))
    with pytest.raises(StudyError, match="ledger"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    assert len(tactical_provider.uploaded) == 4
    tactical_path.write_bytes(saved_intent)
    tactical_provider.anonymous_status = 403
    assert publish(tactical_remote, tactical_path, tactical_course, strict=True) == tactical_link
    assert len(tactical_provider.uploaded) == 4

    from chess_coach.tactical_study_final import check as final_check

    tactical_provider.change_name_on_export = True
    with pytest.raises(StudyError, match="marker"):
        final_check(
            tactical_remote, verified, chapters[:4], verified["chapter_ids"], matches_mainline
        )
    tactical_provider.name = verified["marker"]

    tactical_provider.uploaded[0], tactical_provider.uploaded[1] = (
        tactical_provider.uploaded[1],
        tactical_provider.uploaded[0],
    )
    with pytest.raises(StudyError, match="order"):
        publish(tactical_remote, tactical_path, tactical_course, strict=True)
    tactical_provider.uploaded[0], tactical_provider.uploaded[1] = (
        tactical_provider.uploaded[1],
        tactical_provider.uploaded[0],
    )
    expected = {**chapters[0], "name": tactical_provider.uploaded[0]["name"]}
    original_pgn = tactical_provider.uploaded[0]["pgn"]
    reordered = chess.pgn.read_game(io.StringIO(original_pgn))
    assert reordered is not None
    reordered.variations[0].variations.reverse()
    tactical_provider.uploaded[0]["pgn"] = str(reordered)
    assert matches(expected, tactical_provider.export())
    assert not matches_mainline(expected, tactical_provider.export())
    tactical_provider.uploaded[0]["pgn"] = original_pgn

    before_post = {"study": "abcd1234", "chapters": ["new"]}
    before_path = upload_planning / "before-post.json"
    checks = []

    def stale_before_post():
        checks.append(True)
        if len(checks) == 2:
            raise StudyError("source changed")

    with pytest.raises(StudyError, match="source changed"):
        upload_one(tactical_remote, before_path, before_post, 0, {}, stale_before_post, strict=True)
    assert json.loads(before_path.read_text())["chapters"] == ["new"]
    assert len(tactical_provider.uploaded) == 4

    cooldown_state = {"study": "abcd1234", "chapters": ["new"]}
    cooldown_path = upload_planning / "before-cooldown.json"
    guard_calls = []

    def cooldown_after_save():
        guard_calls.append(True)
        if len(guard_calls) == 2:
            raise StudyError("retry delay")

    tactical_remote.guard = cooldown_after_save
    with pytest.raises(StudyError, match="retry delay"):
        upload_one(tactical_remote, cooldown_path, cooldown_state, 0, {}, lambda: None, strict=True)
    assert json.loads(cooldown_path.read_text())["chapters"] == ["new"]
    tactical_remote.guard = lambda: None

    from chess_coach.study_import_verify import finish

    stale_receipt = {**verified, "complete": False}
    stale_path = upload_planning / "stale-final.json"

    def stale_final():
        raise StudyError("source changed")

    with pytest.raises(StudyError, match="source changed"):
        finish(
            tactical_remote,
            stale_path,
            stale_receipt,
            chapters[:4],
            stale_final,
            matches_mainline,
            True,
        )
    assert not stale_path.exists() and not stale_receipt["complete"]

    displayed = planning / tactical_path.name
    displayed.write_bytes(tactical_path.read_bytes())
    displayed.chmod(0o600)
    planning.chmod(0o700)
    assert tactical_status(tmp_path, "learner")["url"] == tactical_link
    assert tactical_status(tmp_path, "different") is None
    planning.chmod(0o755)
    assert tactical_status(tmp_path, "learner") is None
    planning.chmod(0o700)
    outside_root = tmp_path / "outside-root"
    (outside_root / ".runtime").mkdir(parents=True)
    (outside_root / ".runtime" / "planning").symlink_to(planning)
    assert tactical_status(outside_root, "learner") is None
    assert status(tmp_path)["url"].endswith("/abcd1234/ch000002#0")

    # Tactical exports have separate version intents; ambiguous creates block another version.
    from chess_coach.study_session import locked
    from chess_coach.tactical_study_destination import prepare as prepare_destination
    from chess_coach.tactical_study_intents import intent as tactical_intent

    old_intent = planning / "poc-study-336-intent.json"
    old_intent.chmod(0o600)
    old_bytes = old_intent.read_bytes()
    first_body = {"chapters": [], "version": "first"}
    second_body = {"chapters": [], "version": "second"}
    first_course = {"course": first_body, "course_sha256": preview_hash(first_body)}
    second_course = {"course": second_body, "course_sha256": preview_hash(second_body)}
    first_intent = tactical_intent(planning, first_course["course_sha256"])
    tactical_provider = Provider()
    tactical_remote = Remote("fixture-token", "learner", tactical_provider)

    def cooldown():
        raise StudyError("retry delay")

    blocked = Remote("fixture-token", "learner", tactical_provider, guard=cooldown)
    with pytest.raises(StudyError, match="retry delay"):
        prepare_destination(blocked, first_intent, first_course)
    assert first_intent.exists() and tactical_provider.created == 0
    with pytest.raises(StudyError, match="unknown"):
        prepare_destination(tactical_remote, first_intent, first_course)
    assert tactical_provider.created == 1 and not tactical_provider.uploaded
    with pytest.raises(StudyError, match="another tactical"):
        tactical_intent(planning, second_course["course_sha256"])
    from chess_coach.tactical_study_intents import require_clear

    opening_intent = planning / ("opening-study-" + "f" * 64 + "-intent.json")
    with pytest.raises(StudyError, match="another tactical"):
        require_clear(planning, opening_intent)
    # An unresolved tactical create also blocks a new legacy create.
    legacy_provider = Provider()
    legacy_remote = Remote("fixture-token", "learner", legacy_provider)
    with pytest.raises(StudyError, match="another tactical"):
        publish(legacy_remote, planning / "other-poc-intent.json", course)
    assert legacy_provider.created == 0
    for count in (0, 2):
        tactical_provider.inventory_count = count
        with pytest.raises(StudyError, match="unresolved"):
            prepare_destination(tactical_remote, first_intent, first_course)
    tactical_provider.inventory_count = 1
    tactical_provider.private = False
    with pytest.raises(StudyError, match="privacy"):
        prepare_destination(tactical_remote, first_intent, first_course)
    tactical_provider.private = True
    tactical_provider.owner = "someone-else"
    with pytest.raises(StudyError, match="ownership"):
        prepare_destination(tactical_remote, first_intent, first_course)
    tactical_provider.owner = "learner"
    tactical_provider.settings["shareable"] = "everyone"
    with pytest.raises(StudyError, match="restrictions"):
        prepare_destination(tactical_remote, first_intent, first_course)
    tactical_provider.settings = dict(SETTINGS)
    tactical_provider.empty_id = ""
    with pytest.raises(StudyError, match="invalid Study identifier"):
        prepare_destination(tactical_remote, first_intent, first_course)
    assert json.loads(first_intent.read_text())["create_pending"]
    tactical_provider.empty_id = "empty000"
    assert prepare_destination(tactical_remote, first_intent, first_course) == "abcd1234"
    assert prepare_destination(tactical_remote, first_intent, first_course) == "abcd1234"
    state = json.loads(first_intent.read_text())
    assert state["empty_chapter"] == "empty000" and not state["complete"]
    assert tactical_provider.created == 1 and not tactical_provider.uploaded
    second_intent = tactical_intent(planning, second_course["course_sha256"])
    assert second_intent != first_intent and not second_intent.exists()
    opening_intent.write_text(json.dumps({"study": None, "create_pending": True}))
    opening_intent.chmod(0o600)
    with pytest.raises(StudyError, match="another tactical or opening"):
        tactical_intent(planning, second_course["course_sha256"])
    with pytest.raises(StudyError, match="another tactical or opening"):
        publish(legacy_remote, planning / "another-poc-intent.json", course)
    assert legacy_provider.created == 0
    opening_intent.write_text(json.dumps({"study": "abcd1234", "create_pending": True}))
    second_provider = Provider()
    second_provider.timeout_create = False
    observed = []
    second_remote = Remote(
        "fixture-token",
        "learner",
        second_provider,
        observe=lambda response: observed.append(response.status_code),
    )
    for status_code in (401, 403, 429):
        second_provider.create_status = status_code
        with pytest.raises(StudyError):
            prepare_destination(second_remote, second_intent, second_course)
        assert not json.loads(second_intent.read_text())["create_pending"]
    assert observed[-1] == 429
    second_provider.create_status = None
    assert prepare_destination(second_remote, second_intent, second_course) == "abcd1234"
    assert json.loads(second_intent.read_text())["marker"] != state["marker"]
    assert second_provider.created == 4 and not second_provider.uploaded
    # A freshness failure after the pending marker is saved precedes any POST.
    changing_body = {"chapters": [], "version": "changing"}
    changing_course = {"course": changing_body, "course_sha256": preview_hash(changing_body)}
    changing_intent = tactical_intent(planning, changing_course["course_sha256"])
    changing_provider = Provider()
    changing_remote = Remote("fixture-token", "learner", changing_provider)
    checks = []

    def stale_after_save():
        checks.append(True)
        if len(checks) == 3:
            raise StudyError("source changed")

    with pytest.raises(StudyError, match="source changed"):
        prepare_destination(
            changing_remote, changing_intent, changing_course, check=stale_after_save
        )
    assert len(checks) == 3 and changing_provider.created == 0
    assert not json.loads(changing_intent.read_text())["create_pending"]
    third_body = {"chapters": [], "version": "third"}
    third_course = {"course": third_body, "course_sha256": preview_hash(third_body)}
    third_intent = tactical_intent(planning, third_course["course_sha256"])
    failed_provider = Provider()
    failed_provider.create_status = 500
    failed_remote = Remote("fixture-token", "learner", failed_provider)
    with pytest.raises(StudyError):
        prepare_destination(failed_remote, third_intent, third_course)
    assert json.loads(third_intent.read_text())["create_pending"]
    with pytest.raises(StudyError, match="unresolved"):
        prepare_destination(failed_remote, third_intent, third_course)
    assert failed_provider.created == 1
    assert old_intent.read_bytes() == old_bytes
    with (
        locked(tmp_path / "fixture.sqlite", planning),
        pytest.raises(BlockingIOError),
        locked(tmp_path / "fixture.sqlite", planning),
    ):
        pass

    wrong = Remote("fixture-token", "someone-else", Provider())
    with pytest.raises(StudyError, match="account"):
        publish(wrong, tmp_path / "other.json", course)
