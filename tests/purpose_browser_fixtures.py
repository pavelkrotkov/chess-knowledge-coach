"""Private browser fixtures for diagnostic views."""

from chess_coach.web import create_app
from tests.test_deep_selection import LEARNER


def app(path, subject=LEARNER):
    return create_app(
        db_path=path,
        subject=subject,
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )


def browser_get(client, path, *, login="login"):
    return client.get(
        path, base_url="https://coach.invalid", headers={"Tailscale-User-Login": login}
    )
