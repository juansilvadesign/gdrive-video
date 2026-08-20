"""Host validation and centralized secret redaction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlsplit, urlunsplit

from .errors import integrity_error


class UrlScope(str, Enum):
    METADATA = "metadata"
    MEDIA = "media"


@dataclass(frozen=True, slots=True)
class UrlPolicy:
    """Production host policy with opt-in exact origins for offline tests."""

    metadata_hosts: frozenset[str] = frozenset({"drive.google.com"})
    media_hosts: frozenset[str] = frozenset(
        {"drive.google.com", "drive.usercontent.google.com", "googlevideo.com"}
    )
    media_suffixes: tuple[str, ...] = (".googlevideo.com", ".googleusercontent.com")
    test_origins: frozenset[tuple[str, str, int | None]] = field(default_factory=frozenset)

    def validate(self, url: str, scope: UrlScope) -> str:
        """Return the URL unchanged only after validating its complete origin."""

        if not isinstance(url, str) or not url or len(url) > 8192:
            raise integrity_error("The remote service supplied an invalid or oversized URL.")
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise integrity_error("The remote service supplied an invalid URL.") from None

        host = (parsed.hostname or "").lower().rstrip(".")
        origin = (parsed.scheme.lower(), host, port)
        if origin in self.test_origins:
            if parsed.username is not None or parsed.password is not None:
                raise integrity_error("Credential-bearing URLs are not accepted.")
            return url

        if parsed.scheme.lower() != "https":
            raise integrity_error("An insecure or downgraded remote URL was refused.")
        if parsed.username is not None or parsed.password is not None:
            raise integrity_error("Credential-bearing URLs are not accepted.")
        if port not in (None, 443):
            raise integrity_error("A remote URL with an unexpected port was refused.")
        if not host:
            raise integrity_error("The remote service supplied a URL without a host.")

        if scope is UrlScope.METADATA:
            allowed = host in self.metadata_hosts
        else:
            allowed = host in self.media_hosts or any(
                host.endswith(suffix) and host != suffix.removeprefix(".")
                for suffix in self.media_suffixes
            )
        if not allowed:
            raise integrity_error(
                "A redirect or media URL used an unexpected host and was refused."
            )
        return url


_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_COOKIE_PAIR_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])((?:__Secure-|__Host-)?(?:SID|HSID|SSID|APISID|SAPISID|SIDCC|PSID[A-Z]*))=[^;\s,]+"
)
_HEADER_RE = re.compile(
    r"(?im)\b(cookie|set-cookie|authorization|proxy-authorization)\s*:\s*[^\r\n]+"
)
_ACCOUNT_RE = re.compile(r"/u/\d+(?=/)")


def sanitize_url(url: str) -> str:
    """Keep only a non-secret origin/path representation for diagnostics."""

    try:
        parsed = urlsplit(url)
    except ValueError:
        return "<redacted-url>"
    host = (parsed.hostname or "<unknown-host>").lower()
    try:
        port = parsed.port
    except ValueError:
        return "<redacted-url>"
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    path = _ACCOUNT_RE.sub("/u/<redacted>", parsed.path)
    query = "<redacted>" if parsed.query else ""
    return urlunsplit((parsed.scheme, netloc, path, query, ""))


def redact_text(text: object, secrets: tuple[str, ...] = ()) -> str:
    """Redact known credentials, query strings, account hints, and caller secrets."""

    value = str(text)
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        value = value.replace(secret, "<redacted>")
    value = _HEADER_RE.sub(lambda match: f"{match.group(1)}: <redacted>", value)
    value = _COOKIE_PAIR_RE.sub(lambda match: f"{match.group(1)}=<redacted>", value)
    value = _URL_RE.sub(lambda match: sanitize_url(match.group(0)), value)
    return _ACCOUNT_RE.sub("/u/<redacted>", value)
