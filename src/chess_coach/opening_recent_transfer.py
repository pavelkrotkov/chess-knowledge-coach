"""Read an anonymous fixed range and persist provider retry instructions."""

import time

from .lichess_retry import retry_delay
from .opening_queue_write import write
from .opening_recent_http import validate
from .opening_recent_source import PREFIX_BYTES, URL
from .pipeline_network_response import bounded_body

RETRY_NAME = "opening-standard-rated-2026-10-retry.json"


def receive(client, directory, deadline):
    headers = {"Range": f"bytes=0-{PREFIX_BYTES - 1}", "Accept-Encoding": "identity"}
    with client.stream("GET", URL, headers=headers) as response:
        if response.status_code in (429, 503):
            wait = retry_delay(response, 0, 0)
            write(directory / RETRY_NAME, {"not_before": time.time() + wait})
            raise ValueError("public source requested a retry delay")
        identity = validate(response)
        content = bounded_body(response, PREFIX_BYTES, deadline)
        if len(content) != PREFIX_BYTES:
            raise ValueError("public source range was incomplete")
    return content, identity
