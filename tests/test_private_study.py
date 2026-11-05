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
            return httpx.Response(200, text=self.export(), request=request)
        if path == "/api/study/abcd1234/import-pgn":
            item = kwargs["data"]
            self.uploaded.append(item)
            if self.timeout_upload:
                self.timeout_upload = False
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(200, json={"chapters": [{"id": "new"}]}, request=request)
        raise AssertionError(path)

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


def test_private_publication_reconciles_timeouts_and_rejects_public_destination(tmp_path):
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
