"""The outgoing HTTP client as a FastAPI dependency (tests swap it for a fake one)."""

from collections.abc import Iterator

import httpx

from app.collect import USER_AGENT


def get_http_client() -> Iterator[httpx.Client]:
    """One client per request, closed when the response is sent (the code after yield)."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        yield client
