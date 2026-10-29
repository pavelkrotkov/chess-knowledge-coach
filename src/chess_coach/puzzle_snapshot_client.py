"""Construct the restricted HTTP client."""

import httpx


def make_client(limits):
    return httpx.Client(
        timeout=httpx.Timeout(
            connect=min(limits.connect_timeout, limits.seconds),
            read=min(limits.read_timeout, limits.seconds),
            write=min(limits.read_timeout, limits.seconds),
            pool=min(limits.connect_timeout, limits.seconds),
        ),
        follow_redirects=False,
        trust_env=False,
    )
