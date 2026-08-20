"""Integrity-aware resumable transfer and atomic finalization."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import requests

from .errors import GDriveVideoError, integrity_error
from .files import (
    SIDECAR_SCHEMA,
    OutputPlan,
    ResumeState,
    archive_partial,
    load_resume_state,
    promote_partial,
    write_resume_state,
)
from .http import RETRYABLE_STATUSES, SecureHttpClient, retry_delay
from .models import (
    EXIT_CODES,
    DownloadRequest,
    DownloadResult,
    FailureKind,
    MediaMetadata,
    ProgressCallback,
    ProgressEvent,
)
from .security import UrlScope

CONTENT_RANGE_RE = re.compile(r"^bytes (\d+)-(\d+)/(\d+|\*)$")
UNSATISFIED_RANGE_RE = re.compile(r"^bytes \*/(\d+)$")
CHECKPOINT_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ResponseIdentity:
    total: int | None
    etag: str | None
    last_modified: str | None
    content_type: str
    segment_length: int | None
    segment_end: int | None


def _parse_nonnegative_int(value: str | None, header_name: str) -> int | None:
    if value is None:
        return None
    if not value.isascii() or not value.isdigit():
        raise integrity_error(f"The media response had an invalid {header_name} header.")
    return int(value)


def _base_content_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _accepted_content_type(response_value: str | None, hinted: str | None) -> str:
    response_type = _base_content_type(response_value)
    hinted_type = _base_content_type(hinted)
    if response_type and response_type.startswith("video/"):
        return response_type
    if (
        response_type == "application/octet-stream"
        and hinted_type
        and hinted_type.startswith("video/")
    ):
        return hinted_type
    if response_type is None and hinted_type and hinted_type.startswith("video/"):
        return hinted_type
    raise GDriveVideoError(
        FailureKind.NON_VIDEO,
        "The media response did not have an accepted video content type.",
    )


def _validate_content_encoding(value: str | None) -> None:
    if value and value.strip().lower() != "identity":
        raise integrity_error(
            "An encoded media response was refused because byte ranges would be ambiguous."
        )


def _validated_validator(value: str | None, header_name: str) -> str | None:
    if value is None:
        return None
    if len(value) > 1024 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise integrity_error(f"The media response had an invalid {header_name} header.")
    return value


def _validate_response(
    response: requests.Response,
    *,
    offset: int,
    state: ResumeState | None,
    hinted_content_type: str | None,
) -> ResponseIdentity:
    _validate_content_encoding(response.headers.get("Content-Encoding"))
    content_type = _accepted_content_type(response.headers.get("Content-Type"), hinted_content_type)
    content_length = _parse_nonnegative_int(
        response.headers.get("Content-Length"), "Content-Length"
    )
    etag = _validated_validator(response.headers.get("ETag") or None, "ETag")
    last_modified = _validated_validator(
        response.headers.get("Last-Modified") or None, "Last-Modified"
    )

    if offset == 0:
        if response.status_code != 200:
            raise integrity_error("A fresh media request did not return the required 200 response.")
        total = content_length
        segment_end = total - 1 if total is not None and total > 0 else None
    else:
        if response.status_code == 200:
            raise integrity_error(
                "The server ignored the resume range. The existing partial was "
                "preserved; use --restart to archive it."
            )
        if response.status_code != 206:
            raise integrity_error("A resume request did not return the required 206 response.")
        match = CONTENT_RANGE_RE.fullmatch(response.headers.get("Content-Range", ""))
        if not match:
            raise integrity_error("The resume response had a malformed Content-Range header.")
        start, end = int(match.group(1)), int(match.group(2))
        if start != offset or end < start:
            raise integrity_error("The resume response did not begin at the local byte count.")
        total = None if match.group(3) == "*" else int(match.group(3))
        if total is not None and (end >= total or total <= offset):
            raise integrity_error("The resume response advertised an impossible remote total.")
        segment_length = end - start + 1
        if content_length is not None and content_length != segment_length:
            raise integrity_error("Content-Length did not match the resumed byte range.")
        content_length = segment_length
        segment_end = end

    if state is not None:
        if state.expected_total is not None and (total is None or total != state.expected_total):
            raise integrity_error("The remote byte total changed since the partial was created.")
        if state.etag is not None and etag != state.etag:
            raise integrity_error("The remote ETag changed or disappeared during resume.")
        if state.last_modified is not None and last_modified != state.last_modified:
            raise integrity_error(
                "The remote Last-Modified value changed or disappeared during resume."
            )
        if _base_content_type(state.content_type) != _base_content_type(content_type):
            raise integrity_error("The remote media content type changed during resume.")

    return ResponseIdentity(
        total=total,
        etag=etag,
        last_modified=last_modified,
        content_type=content_type,
        segment_length=content_length,
        segment_end=segment_end,
    )


def _if_range(state: ResumeState) -> str | None:
    if state.etag and not state.etag.startswith("W/"):
        return state.etag
    return state.last_modified


def _looks_like_error_body(chunk: bytes) -> bool:
    leading = chunk.lstrip()[:64].lower()
    return leading.startswith((b"<!doctype html", b"<html", b"<?xml", b"{", b"["))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise GDriveVideoError(
            FailureKind.FILESYSTEM,
            "The completed partial could not be read for its integrity check.",
        ) from None
    return digest.hexdigest()


def _open_partial(path: Path, *, offset: int) -> BinaryIO:
    flags = os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    before = None
    if offset == 0:
        try:
            before = path.lstat()
        except FileNotFoundError:
            flags |= os.O_CREAT | os.O_EXCL
        else:
            if (
                stat.S_ISLNK(before.st_mode)
                or not stat.S_ISREG(before.st_mode)
                or before.st_size != 0
            ):
                raise GDriveVideoError(
                    FailureKind.CONFLICT, "The partial output changed before transfer."
                )
    else:
        flags |= os.O_APPEND
        try:
            before = path.lstat()
        except FileNotFoundError:
            raise GDriveVideoError(
                FailureKind.CONFLICT, "The partial disappeared before resume."
            ) from None
        if (
            stat.S_ISLNK(before.st_mode)
            or not stat.S_ISREG(before.st_mode)
            or before.st_size != offset
        ):
            raise GDriveVideoError(FailureKind.CONFLICT, "The partial changed before resume.")
    try:
        descriptor = os.open(path, flags, 0o600)
        current = os.fstat(descriptor)
        if before is not None and (current.st_dev, current.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            os.close(descriptor)
            raise GDriveVideoError(FailureKind.CONFLICT, "The partial changed while it was opened.")
        return os.fdopen(descriptor, "ab" if offset else "wb", buffering=0)
    except GDriveVideoError:
        raise
    except OSError:
        raise GDriveVideoError(
            FailureKind.FILESYSTEM, "The partial output could not be opened safely."
        ) from None


def _validate_416(response: requests.Response, state: ResumeState, local_size: int) -> None:
    match = UNSATISFIED_RANGE_RE.fullmatch(response.headers.get("Content-Range", ""))
    if not match:
        raise integrity_error("The 416 response did not contain a valid remote total.")
    remote_total = int(match.group(1))
    if remote_total != local_size or state.expected_total != remote_total:
        raise integrity_error("The 416 remote total did not match the partial and sidecar.")
    if state.etag is not None and response.headers.get("ETag") != state.etag:
        raise integrity_error("The 416 response did not match the stored ETag.")
    if (
        state.last_modified is not None
        and response.headers.get("Last-Modified") != state.last_modified
    ):
        raise integrity_error("The 416 response did not match the stored Last-Modified value.")


class TransferClient:
    """Download one discovered media URL while preserving truthful state."""

    def __init__(
        self,
        session: requests.Session,
        http: SecureHttpClient,
        *,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.session = session
        self.http = http
        self.sleep = sleep or __import__("time").sleep

    def download(
        self,
        request: DownloadRequest,
        metadata: MediaMetadata,
        plan: OutputPlan,
        *,
        rediscover: Callable[[], MediaMetadata],
        progress: ProgressCallback | None = None,
    ) -> DownloadResult:
        if request.restart:
            archive_partial(plan)
        expected_sha256 = (
            request.expected_sha256.lower() if request.expected_sha256 is not None else None
        )
        state = load_resume_state(plan, metadata.source_id)
        if state is not None and state.expected_sha256 != expected_sha256:
            raise GDriveVideoError(
                FailureKind.CONFLICT,
                "The requested digest does not match the existing partial's contract.",
            )
        if (
            state is not None
            and state.completed_bytes > 0
            and state.expected_total is None
            and state.etag is None
            and state.last_modified is None
        ):
            raise GDriveVideoError(
                FailureKind.CONFLICT,
                "This unknown-length partial has no validator and cannot be resumed "
                "safely; use --restart.",
            )

        current_metadata = metadata
        last_kind = FailureKind.NETWORK
        for attempt in range(1, request.retries.max_attempts + 1):
            offset = state.completed_bytes if state else 0
            headers: dict[str, str] = {"Accept-Encoding": "identity"}
            if offset > 0:
                if state is None:
                    raise integrity_error("Resume state disappeared before the range request.")
                headers["Range"] = f"bytes={offset}-"
                validator = _if_range(state)
                if validator:
                    headers["If-Range"] = validator

            try:
                response = self.http.request(
                    self.session,
                    "GET",
                    current_metadata.playback_url,
                    scope=UrlScope.MEDIA,
                    headers=headers,
                    stream=True,
                    timeouts=request.timeouts,
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt >= request.retries.max_attempts:
                    raise GDriveVideoError(
                        FailureKind.NETWORK,
                        "The media transfer failed after bounded retries; the partial "
                        "is preserved.",
                    ) from None
                self._wait(request, attempt)
                current_metadata = rediscover()
                continue

            try:
                if response.status_code in RETRYABLE_STATUSES:
                    last_kind = (
                        FailureKind.THROTTLED
                        if response.status_code == 429
                        else FailureKind.NETWORK
                    )
                    if attempt >= request.retries.max_attempts:
                        raise GDriveVideoError(
                            last_kind,
                            "The media service remained unavailable after bounded retries; "
                            "the partial is preserved.",
                        )
                    self.sleep(
                        retry_delay(
                            response.headers.get("Retry-After"),
                            attempt=attempt,
                            base_delay=request.retries.base_delay,
                            maximum_delay=request.retries.maximum_delay,
                        )
                    )
                    current_metadata = rediscover()
                    continue
                if response.status_code in (401, 403):
                    if attempt >= request.retries.max_attempts:
                        raise GDriveVideoError(
                            FailureKind.EXPIRED_URL,
                            "The signed playback authorization expired or was refused "
                            "after rediscovery.",
                        )
                    current_metadata = rediscover()
                    continue
                if response.status_code == 404:
                    raise GDriveVideoError(
                        FailureKind.AUTHORIZATION,
                        "The media file is unavailable to the current account.",
                    )
                if response.status_code == 416:
                    if state is None or offset == 0:
                        raise integrity_error("An unexpected 416 response was refused.")
                    _validate_416(response, state, offset)
                    return self._complete(request, plan, state, progress)
                if response.status_code not in (200, 206):
                    raise GDriveVideoError(
                        FailureKind.NETWORK, "The media service returned an unexpected status."
                    )

                identity = _validate_response(
                    response,
                    offset=offset,
                    state=state,
                    hinted_content_type=current_metadata.content_type,
                )
                if state is None:
                    state = ResumeState(
                        schema_version=SIDECAR_SCHEMA,
                        source_id=metadata.source_id,
                        expected_total=identity.total,
                        etag=identity.etag,
                        last_modified=identity.last_modified,
                        content_type=identity.content_type,
                        expected_sha256=expected_sha256,
                        completed_bytes=0,
                    )
                elif state.expected_total is None and identity.total is not None:
                    state.expected_total = identity.total

                try:
                    self._consume_response(
                        response,
                        request=request,
                        plan=plan,
                        state=state,
                        identity=identity,
                        offset=offset,
                        progress=progress,
                    )
                except (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                ):
                    if attempt >= request.retries.max_attempts:
                        raise GDriveVideoError(
                            FailureKind.NETWORK,
                            "The media stream ended unexpectedly after bounded retries; "
                            "the partial is preserved.",
                        ) from None
                    self._wait(request, attempt)
                    current_metadata = rediscover()
                    continue

                if (
                    state.expected_total is not None
                    and state.completed_bytes < state.expected_total
                ):
                    if attempt >= request.retries.max_attempts:
                        raise GDriveVideoError(
                            FailureKind.NETWORK,
                            "The media stream ended before the expected byte count; "
                            "the partial is preserved.",
                        )
                    current_metadata = rediscover()
                    continue
                return self._complete(request, plan, state, progress)
            finally:
                response.close()

        raise GDriveVideoError(last_kind, "The media transfer did not complete.")

    def _wait(self, request: DownloadRequest, attempt: int) -> None:
        self.sleep(
            retry_delay(
                None,
                attempt=attempt,
                base_delay=request.retries.base_delay,
                maximum_delay=request.retries.maximum_delay,
            )
        )

    def _consume_response(
        self,
        response: requests.Response,
        *,
        request: DownloadRequest,
        plan: OutputPlan,
        state: ResumeState,
        identity: ResponseIdentity,
        offset: int,
        progress: ProgressCallback | None,
    ) -> None:
        response_bytes = 0
        checkpoint_at = offset + CHECKPOINT_BYTES
        handle = _open_partial(plan.partial, offset=offset)
        try:
            if offset == 0:
                write_resume_state(plan.sidecar, state)
            for chunk in response.iter_content(chunk_size=request.chunk_size):
                if not chunk:
                    continue
                if offset == 0 and response_bytes == 0 and _looks_like_error_body(chunk):
                    raise integrity_error(
                        "The media response body looked like HTML or JSON rather than video."
                    )
                try:
                    written = handle.write(chunk)
                except OSError:
                    raise GDriveVideoError(
                        FailureKind.FILESYSTEM,
                        "Writing the partial failed; recoverable bytes and sidecar were "
                        "preserved where possible.",
                    ) from None
                if written != len(chunk):
                    raise GDriveVideoError(
                        FailureKind.FILESYSTEM,
                        "A short filesystem write occurred; the transfer was stopped.",
                    )
                response_bytes += written
                state.completed_bytes += written
                if progress:
                    progress(ProgressEvent(state.completed_bytes, state.expected_total))
                if state.completed_bytes >= checkpoint_at:
                    handle.flush()
                    write_resume_state(plan.sidecar, state)
                    checkpoint_at = state.completed_bytes + CHECKPOINT_BYTES
            handle.flush()
            os.fsync(handle.fileno())
            write_resume_state(plan.sidecar, state)
        except KeyboardInterrupt:
            try:
                handle.flush()
                os.fsync(handle.fileno())
                state.completed_bytes = os.fstat(handle.fileno()).st_size
                write_resume_state(plan.sidecar, state)
            except (OSError, GDriveVideoError):
                pass
            raise GDriveVideoError(
                FailureKind.CANCELLED,
                "Transfer cancelled; the partial and its resume state were preserved.",
            ) from None
        finally:
            handle.close()

        if response_bytes == 0 and (
            state.expected_total is None or state.completed_bytes < state.expected_total
        ):
            raise integrity_error("The media response ended without any video bytes.")
        if identity.segment_length is not None and response_bytes != identity.segment_length:
            raise requests.exceptions.ChunkedEncodingError("advertised segment length mismatch")
        if identity.segment_end is not None and state.completed_bytes != identity.segment_end + 1:
            raise integrity_error("The completed local range did not match Content-Range.")

    def _complete(
        self,
        request: DownloadRequest,
        plan: OutputPlan,
        state: ResumeState,
        progress: ProgressCallback | None,
    ) -> DownloadResult:
        try:
            actual_size = plan.partial.stat().st_size
        except OSError:
            raise GDriveVideoError(
                FailureKind.FILESYSTEM, "The completed partial could not be inspected."
            ) from None
        if actual_size <= 0:
            raise integrity_error("An empty partial cannot be promoted as a video.")
        if state.expected_total is not None and actual_size != state.expected_total:
            raise integrity_error(
                "The completed byte count did not match the expected remote total."
            )
        digest = _sha256(plan.partial)
        if request.expected_sha256 and digest != request.expected_sha256.lower():
            raise integrity_error("The completed file did not match the requested SHA-256 digest.")
        sidecar_removed = promote_partial(plan, overwrite=request.overwrite)
        if progress:
            progress(ProgressEvent(actual_size, state.expected_total or actual_size, "complete"))
        return DownloadResult(
            kind=FailureKind.SUCCESS,
            message=(
                "Download completed and atomically promoted after integrity checks."
                if sidecar_removed
                else (
                    "Download completed and atomically promoted; stale sidecar cleanup is required."
                )
            ),
            exit_code=EXIT_CODES[FailureKind.SUCCESS],
            final_path=plan.final,
            completed_bytes=actual_size,
            sha256=digest,
        )
