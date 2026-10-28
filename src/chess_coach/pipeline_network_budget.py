"""Enforce request, byte, retry-sleep and elapsed network limits."""

import time

import httpx

from .pipeline_network_response import BudgetExceeded, bounded_body, observe_before_timeout


class BoundedClient:
    def __init__(
        self, client, maximum: int, deadline: float, byte_limit: int, timeout: float, guard, observe
    ):
        self.client = client
        self.remaining = maximum
        self.deadline = deadline
        self.byte_limit = byte_limit
        self.timeout = timeout
        self.guard = guard
        self.observe = observe

    def get(self, url: str, **kwargs):
        self.guard()
        remaining = self.deadline - time.monotonic()
        if self.remaining <= 0 or remaining <= 0:
            raise BudgetExceeded("network budget exhausted")
        self.remaining -= 1
        with self.client.stream(
            "GET", url, timeout=min(self.timeout, remaining), **kwargs
        ) as response:
            observe_before_timeout(self.observe, response)
            content = bounded_body(response, self.byte_limit, self.deadline)
            self.byte_limit -= len(content)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=content,
                request=response.request,
            )


class BoundedSleep:
    def __init__(self, maximum: float, deadline: float):
        self.remaining = maximum
        self.deadline = deadline

    def __call__(self, seconds: float) -> None:
        if seconds > self.remaining or seconds > self.deadline - time.monotonic():
            raise BudgetExceeded("network retry budget exhausted")
        self.remaining -= seconds
        time.sleep(seconds)
