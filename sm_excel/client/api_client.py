"""Low-level HTTP helpers for the SurveyMonkey REST API."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30  # seconds per HTTP request
_RETRY_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds; doubled on each retry


def generate_headers(token: str) -> dict[str, str]:
    """Build the HTTP headers required by the SurveyMonkey API.

    Args:
        token: A valid OAuth 2.0 Bearer token.

    Returns:
        A dictionary containing Authorization and Content-Type headers.
    """
    if not token or not isinstance(token, str):
        raise ValueError("A non-empty string token is required.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def request_get(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Perform a robust HTTP GET to the SurveyMonkey API.

    Retries on transient server errors and rate-limit responses (429).
    Exponential back-off is applied between retries.

    Args:
        url:     Full request URL.
        headers: Auth/content headers (from :func:`generate_headers`).
        params:  Optional query-string parameters.
        timeout: Per-request timeout in seconds.

    Returns:
        Parsed JSON response body as a dictionary.

    Raises:
        requests.HTTPError: on non-retryable 4xx / final 5xx responses.
        requests.ConnectionError: on network-level failures.
        ValueError: if the response body is not valid JSON.
    """
    params = params or {}
    attempt = 0
    wait = _RETRY_BACKOFF

    while attempt <= _MAX_RETRIES:
        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=timeout
            )
        except requests.ConnectionError as exc:
            logger.error("Network error on GET %s: %s", url, exc)
            raise

        if response.status_code in _RETRY_CODES:
            retry_after = float(
                response.headers.get("Retry-After", wait)
            )
            logger.warning(
                "HTTP %s on GET %s – retrying in %.1fs (attempt %d/%d)",
                response.status_code,
                url,
                retry_after,
                attempt + 1,
                _MAX_RETRIES,
            )
            time.sleep(retry_after)
            wait *= 2
            attempt += 1
            continue

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.error("HTTP error on GET %s: %s", url, exc)
            raise

        try:
            return response.json()
        except ValueError as exc:
            logger.error("Invalid JSON from GET %s: %s", url, exc)
            raise

    # All retries exhausted
    response.raise_for_status()
    return {}  # unreachable, satisfies type checkers


def get_all_pages(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Fetch every page of a paginated SurveyMonkey collection.

    The SurveyMonkey API uses ``page`` and ``per_page`` query parameters and
    returns a ``links.next`` URL when more pages are available.

    Args:
        url:       First-page URL of the collection endpoint.
        headers:   Auth headers.
        params:    Additional query parameters (merged with pagination params).
        page_size: Items per page (max 100 for most endpoints).

    Returns:
        A flat list of all ``data`` items from every page.
    """
    params = dict(params or {})
    params.setdefault("per_page", page_size)
    params.setdefault("page", 1)

    all_items: list[dict[str, Any]] = []

    while url:
        body = request_get(url, headers=headers, params=params)
        items = body.get("data", [])
        all_items.extend(items)

        # Follow the next-page link if present; clear params to avoid
        # duplicate query-string keys on subsequent requests.
        next_url: str | None = (
            body.get("links", {}).get("next") or None
        )
        url = next_url  # type: ignore[assignment]
        params = {}     # next URL already contains pagination params

    return all_items
