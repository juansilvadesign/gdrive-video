"""Bounded, structured parsing and retrieval of Drive media metadata."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from urllib.parse import parse_qs, parse_qsl, quote, urlsplit

import requests

from .errors import GDriveVideoError, integrity_error
from .http import RETRYABLE_STATUSES, SecureHttpClient, retry_delay
from .models import FailureKind, MediaMetadata, RetryPolicy, Timeouts
from .security import UrlPolicy, UrlScope

MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_METADATA_FIELDS = 512
STREAM_FIELDS = frozenset({"fmt_stream_map", "adaptive_fmts", "url_encoded_fmt_stream_map"})


def _content_type_from_url(url: str) -> str | None:
    values = parse_qs(urlsplit(url).query, max_num_fields=100)
    for key in ("mime", "type"):
        if values.get(key):
            return values[key][0].split(";", 1)[0].strip().lower() or None
    return None


def _stream_map_entries(value: str) -> Iterable[tuple[str, str | None]]:
    """Parse documented stream-map record grammars after bounded form decoding."""

    if len(value.encode("utf-8")) > MAX_METADATA_BYTES:
        raise integrity_error("Drive metadata contains an oversized stream field.")
    # The outer application/x-www-form-urlencoded parser has already decoded
    # exactly one layer. Do not decode the embedded signed URL again: changing
    # %2C into a literal comma (for example) can invalidate its signature.
    decoded = value
    if "|" in decoded:
        records = re.split(r",(?=\d+\|)", decoded)
        for record in records:
            itag, separator, url = record.partition("|")
            if separator and itag.isdigit() and url.startswith(("https://", "http://")):
                yield url, _content_type_from_url(url)
        return

    for record in re.split(r",(?=(?:itag|url)=)", decoded):
        try:
            descriptor = parse_qs(
                record,
                keep_blank_values=True,
                strict_parsing=False,
                max_num_fields=100,
            )
        except ValueError:
            continue
        urls = descriptor.get("url", [])
        for url in urls:
            candidate = url
            media_type = None
            types = descriptor.get("type", [])
            if types:
                media_type = types[0].split(";", 1)[0].strip().lower() or None
            yield candidate, media_type or _content_type_from_url(candidate)


def _player_response_entries(value: str) -> Iterable[tuple[str, str | None]]:
    decoded = value
    try:
        payload = json.loads(decoded)
    except (json.JSONDecodeError, TypeError):
        return
    streaming = payload.get("streamingData") if isinstance(payload, dict) else None
    if not isinstance(streaming, dict):
        return
    for group in ("formats", "adaptiveFormats"):
        entries = streaming.get(group, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
                continue
            mime = entry.get("mimeType")
            content_type = mime.split(";", 1)[0].lower() if isinstance(mime, str) else None
            yield entry["url"], content_type


def parse_drive_metadata(
    body: bytes,
    *,
    source_id: str,
    policy: UrlPolicy,
    credentials_supplied: bool,
) -> MediaMetadata:
    """Parse a bounded form response without retaining response snippets."""

    if not body:
        raise integrity_error("Drive returned an empty metadata response.")
    if len(body) > MAX_METADATA_BYTES:
        raise integrity_error("Drive metadata exceeded the 2 MiB safety limit.")
    leading = body.lstrip()[:32].lower()
    if leading.startswith((b"<!doctype html", b"<html", b"<?xml")):
        kind = FailureKind.AUTHENTICATION if credentials_supplied else FailureKind.AUTHORIZATION
        raise GDriveVideoError(
            kind, "Drive returned a login or HTML response instead of media metadata."
        )
    try:
        text = body.decode("utf-8")
        pairs = parse_qsl(
            text,
            keep_blank_values=True,
            strict_parsing=False,
            max_num_fields=MAX_METADATA_FIELDS,
        )
    except (UnicodeDecodeError, ValueError):
        raise integrity_error("Drive returned malformed or oversized metadata.") from None

    fields: dict[str, list[str]] = {}
    for key, value in pairs:
        fields.setdefault(key, []).append(value)

    status = (fields.get("status") or [""])[0].lower()
    reason = " ".join(fields.get("reason", [])).lower()
    if status == "fail":
        if any(word in reason for word in ("processing", "transcod", "not ready")):
            raise GDriveVideoError(FailureKind.PROCESSING, "The Drive video is still processing.")
        if any(word in reason for word in ("login", "sign in", "cookie", "authentication")):
            raise GDriveVideoError(
                FailureKind.AUTHENTICATION, "Drive authentication failed or expired."
            )
        if any(word in reason for word in ("permission", "forbidden", "access", "denied")):
            raise GDriveVideoError(
                FailureKind.AUTHORIZATION, "The current account is not authorized for this file."
            )

    titles = [value for value in fields.get("title", []) if value]
    if len(set(titles)) > 1:
        raise integrity_error("Drive returned conflicting titles for one file.")
    title = titles[0] if titles else None

    candidates: list[tuple[str, str | None]] = []
    for key in STREAM_FIELDS:
        for value in fields.get(key, []):
            candidates.extend(_stream_map_entries(value))
    for value in fields.get("player_response", []):
        candidates.extend(_player_response_entries(value))
    for value in fields.get("url", []):
        candidates.append((value, _content_type_from_url(value)))

    for candidate, content_type in candidates:
        try:
            policy.validate(candidate, UrlScope.MEDIA)
        except GDriveVideoError:
            # An explicit stream on an unknown host is a security failure, not a
            # reason to silently choose a later candidate.
            raise
        return MediaMetadata(
            source_id=source_id,
            playback_url=candidate,
            title=title,
            content_type=content_type,
        )

    if status == "fail":
        raise GDriveVideoError(
            FailureKind.AUTHORIZATION,
            "Drive did not authorize a downloadable media response for this file.",
        )
    raise GDriveVideoError(
        FailureKind.NON_VIDEO,
        "Drive returned no downloadable video stream; the file may be non-video "
        "or still unavailable.",
    )


class DiscoveryClient:
    """Retrieve and parse Drive metadata with bounded retry behavior."""

    def __init__(
        self,
        session: requests.Session,
        http: SecureHttpClient,
        policy: UrlPolicy,
        *,
        credentials_supplied: bool = False,
        endpoint_template: str = (
            "https://drive.google.com/u/{account_index}/get_video_info"
            "?docid={source_id}&drive_originator_app=303"
        ),
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.session = session
        self.http = http
        self.policy = policy
        self.credentials_supplied = credentials_supplied
        self.endpoint_template = endpoint_template
        self.sleep = sleep or __import__("time").sleep

    def discover(
        self,
        source_id: str,
        account_index: int,
        *,
        timeouts: Timeouts,
        retries: RetryPolicy,
    ) -> MediaMetadata:
        url = self.endpoint_template.format(
            account_index=account_index,
            source_id=quote(source_id, safe=""),
        )
        for attempt in range(1, retries.max_attempts + 1):
            try:
                response = self.http.request(
                    self.session,
                    "GET",
                    url,
                    scope=UrlScope.METADATA,
                    stream=True,
                    timeouts=timeouts,
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt == retries.max_attempts:
                    raise GDriveVideoError(
                        FailureKind.NETWORK,
                        "Drive metadata could not be reached after bounded retries.",
                    ) from None
                self.sleep(
                    retry_delay(
                        None,
                        attempt=attempt,
                        base_delay=retries.base_delay,
                        maximum_delay=retries.maximum_delay,
                    )
                )
                continue

            try:
                if response.status_code in RETRYABLE_STATUSES:
                    if attempt == retries.max_attempts:
                        kind = (
                            FailureKind.THROTTLED
                            if response.status_code == 429
                            else FailureKind.NETWORK
                        )
                        raise GDriveVideoError(
                            kind,
                            "Drive metadata remained unavailable after bounded retries.",
                        )
                    delay = retry_delay(
                        response.headers.get("Retry-After"),
                        attempt=attempt,
                        base_delay=retries.base_delay,
                        maximum_delay=retries.maximum_delay,
                    )
                    self.sleep(delay)
                    continue
                if response.status_code == 401:
                    raise GDriveVideoError(
                        FailureKind.AUTHENTICATION, "Drive authentication failed or expired."
                    )
                if response.status_code in (403, 404):
                    raise GDriveVideoError(
                        FailureKind.AUTHORIZATION,
                        "The current account is not authorized for this Drive file.",
                    )
                if response.status_code != 200:
                    raise GDriveVideoError(
                        FailureKind.NETWORK,
                        "Drive returned an unexpected metadata status.",
                    )

                data = bytearray()
                try:
                    for chunk in response.iter_content(64 * 1024):
                        data.extend(chunk)
                        if len(data) > MAX_METADATA_BYTES:
                            raise integrity_error("Drive metadata exceeded the 2 MiB safety limit.")
                except requests.RequestException:
                    if attempt == retries.max_attempts:
                        raise GDriveVideoError(
                            FailureKind.NETWORK,
                            "Drive metadata ended unexpectedly after bounded retries.",
                        ) from None
                    self.sleep(
                        retry_delay(
                            None,
                            attempt=attempt,
                            base_delay=retries.base_delay,
                            maximum_delay=retries.maximum_delay,
                        )
                    )
                    continue
                return parse_drive_metadata(
                    bytes(data),
                    source_id=source_id,
                    policy=self.policy,
                    credentials_supplied=self.credentials_supplied,
                )
            finally:
                response.close()

        raise GDriveVideoError(FailureKind.NETWORK, "Drive metadata could not be retrieved.")
