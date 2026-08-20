"""Redirect-safe HTTP primitives and deterministic retry timing."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests

from .errors import integrity_error
from .models import Timeouts
from .security import UrlPolicy, UrlScope

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "host", "proxy-authorization"})


def _strip_sensitive_headers(headers: dict[str, str]) -> None:
    for name in tuple(headers):
        if name.lower() in SENSITIVE_HEADERS:
            headers.pop(name)


class SecureHttpClient:
    """Issue one request while validating every redirect before following it."""

    def __init__(self, policy: UrlPolicy, *, max_redirects: int = 5) -> None:
        self.policy = policy
        self.max_redirects = max_redirects

    def request(
        self,
        session: requests.Session,
        method: str,
        url: str,
        *,
        scope: UrlScope,
        headers: Mapping[str, str] | None = None,
        stream: bool = False,
        timeouts: Timeouts | None = None,
    ) -> requests.Response:
        effective_timeouts = timeouts or Timeouts()
        current_url = self.policy.validate(url, scope)
        current_method = method.upper()
        safe_headers = dict(headers or {})
        if scope is UrlScope.MEDIA:
            # The signed playback URL is the media authorization. Callers cannot
            # accidentally add a second credential channel to the cookie-free
            # media session.
            _strip_sensitive_headers(safe_headers)

        for hop in range(self.max_redirects + 1):
            if scope is UrlScope.MEDIA:
                # A media response may seed a cookie for a later hop or retry.
                # Signed URLs authorize media; every media request stays cookieless.
                session.cookies.clear()
            response = session.request(
                current_method,
                current_url,
                headers=safe_headers,
                stream=stream,
                timeout=effective_timeouts.as_requests_tuple(),
                allow_redirects=False,
            )
            if response.status_code not in REDIRECT_STATUSES:
                return response
            if hop >= self.max_redirects:
                response.close()
                raise integrity_error("The remote service exceeded the redirect limit.")

            location = response.headers.get("Location")
            if not location:
                response.close()
                raise integrity_error("The remote service returned a redirect without a location.")
            next_url = urljoin(current_url, location)
            try:
                self.policy.validate(next_url, scope)
            except Exception:
                response.close()
                raise
            response.close()

            # Never carry caller-supplied credentials across a redirect. Cookie-jar
            # scoping is applied afresh by requests for the validated destination.
            _strip_sensitive_headers(safe_headers)
            if response.status_code == 303 or (
                response.status_code in (301, 302) and current_method not in ("GET", "HEAD")
            ):
                current_method = "GET"
            current_url = next_url

        raise integrity_error("The remote service exceeded the redirect limit.")


def retry_delay(
    retry_after: str | None,
    *,
    attempt: int,
    base_delay: float,
    maximum_delay: float,
    now: datetime | None = None,
) -> float:
    """Return bounded Retry-After or exponential backoff seconds."""

    fallback = min(maximum_delay, base_delay * (2 ** max(attempt - 1, 0)))
    if not retry_after:
        return fallback
    try:
        seconds = float(retry_after.strip())
    except ValueError:
        try:
            target = parsedate_to_datetime(retry_after)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            reference = now or datetime.now(timezone.utc)
            seconds = (target - reference).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return fallback
    if seconds < 0:
        return 0.0
    return min(maximum_delay, seconds)
