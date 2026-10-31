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
        self.timeout_create = True
        self.timeout_upload = True
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
            rows = [{"id": "abcd1234", "name": self.name}] if self.name else []
            return httpx.Response(200, text="\n".join(map(json.dumps, rows)), request=request)
        if path == "/api/study" and method == "POST":
            self.created += 1
            self.name = kwargs["data"]["name"]
            if self.timeout_create:
                self.timeout_create = False
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(200, json={"id": "abcd1234"}, request=request)
        if path.startswith("/study/abcd1234"):
            chapters = [{"id": "empty", "name": "Empty"}]
            chapters.extend(
                {"id": f"ch{i:06d}", "name": item["name"]} for i, item in enumerate(self.uploaded)
            )
            value = {
                "study": {
                    "id": "abcd1234",
                    "name": self.name,
                    "ownerId": "learner",
                    "visibility": "private" if self.private else "public",
                    "settings": SETTINGS,
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

    wrong = Remote("fixture-token", "someone-else", Provider())
    with pytest.raises(StudyError, match="account"):
        publish(wrong, tmp_path / "other.json", course)
