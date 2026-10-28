"""Bound network requests, elapsed time, response size and retry sleeps."""

import time

import httpx

from .lichess import LichessClient
from .pipeline_config import PipelineConfig
from .pipeline_network_budget import BoundedClient, BoundedSleep
from .pipeline_network_budget import BudgetExceeded as BudgetExceeded
from .pipeline_network_privacy import private_network_logs


def sync_games(db, config: PipelineConfig, *, token: str | None = None, transport=None):
    deadline = time.monotonic() + config.network_seconds
    with (
        private_network_logs(),
        httpx.Client(
            timeout=config.network_timeout,
            transport=transport,
            headers={"Accept-Encoding": "identity"},
        ) as client,
    ):
        bounded = BoundedClient(
            client, config.network_requests, deadline, config.network_bytes, config.network_timeout
        )
        lichess = LichessClient(
            token=token,
            client=bounded,
            retries=config.network_retries,
            sleeper=BoundedSleep(config.network_sleep, deadline),
        )
        result = lichess.sync_user(
            db, config.learner, max_games=config.max_games, page_size=config.page_size
        )
        result["http_requests"] = config.network_requests - bounded.remaining
        result["http_bytes"] = config.network_bytes - bounded.byte_limit
        return result
