"""UI-neutral orchestration of discovery, planning, and transfer."""

from __future__ import annotations

import re
from collections.abc import Callable

import requests

from .discovery import DiscoveryClient
from .errors import GDriveVideoError, invalid_input
from .files import OutputPlan, plan_output
from .http import SecureHttpClient
from .input import parse_drive_id
from .models import (
    EXIT_CODES,
    DownloadRequest,
    DownloadResult,
    FailureKind,
    MediaMetadata,
    ProgressCallback,
)
from .security import UrlPolicy, redact_text
from .transfer import TransferClient

MIN_CHUNK_SIZE = 1024
MAX_CHUNK_SIZE = 8 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def validate_request(request: DownloadRequest) -> str:
    """Validate all non-I/O request fields before network/filesystem mutation."""

    source_id = parse_drive_id(request.source)
    if (
        not isinstance(request.chunk_size, int)
        or isinstance(request.chunk_size, bool)
        or not MIN_CHUNK_SIZE <= request.chunk_size <= MAX_CHUNK_SIZE
    ):
        raise invalid_input(
            f"Chunk size must be an integer from {MIN_CHUNK_SIZE} to {MAX_CHUNK_SIZE} bytes."
        )
    if (
        not isinstance(request.account_index, int)
        or isinstance(request.account_index, bool)
        or not 0 <= request.account_index <= 99
    ):
        raise invalid_input("Google account index must be an integer from 0 to 99.")
    if not (0 < request.timeouts.connect <= 300 and 0 < request.timeouts.read <= 3600):
        raise invalid_input(
            "Connect/read timeouts must be positive and within their safety bounds."
        )
    if not 1 <= request.retries.max_attempts <= 5:
        raise invalid_input("Retry attempts must be between 1 and 5.")
    if request.retries.base_delay < 0 or request.retries.maximum_delay < 0:
        raise invalid_input("Retry delays cannot be negative.")
    if request.expected_sha256 and not SHA256_RE.fullmatch(request.expected_sha256):
        raise invalid_input("Expected SHA-256 must contain exactly 64 hexadecimal characters.")
    return source_id


class DownloadService:
    """One service instance owns no UI and prints nothing."""

    def __init__(
        self,
        metadata_session: requests.Session,
        media_session: requests.Session,
        *,
        policy: UrlPolicy | None = None,
        credentials_supplied: bool = False,
        endpoint_template: str | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.policy = policy or UrlPolicy()
        self.http = SecureHttpClient(self.policy)
        discovery_kwargs: dict[str, str] = {}
        if endpoint_template is not None:
            discovery_kwargs["endpoint_template"] = endpoint_template
        self.discovery = DiscoveryClient(
            metadata_session,
            self.http,
            self.policy,
            credentials_supplied=credentials_supplied,
            sleep=sleep,
            **discovery_kwargs,
        )
        self.transfer = TransferClient(media_session, self.http, sleep=sleep)

    def execute(
        self,
        request: DownloadRequest,
        *,
        progress: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Return a typed redacted result for every expected failure."""

        plan: OutputPlan | None = None
        source_id: str | None = None
        try:
            source_id = validate_request(request)
            metadata = self.discovery.discover(
                source_id,
                request.account_index,
                timeouts=request.timeouts,
                retries=request.retries,
            )
            plan = plan_output(
                output=request.output,
                title=metadata.title,
                source_id=source_id,
                content_type=metadata.content_type,
                overwrite=request.overwrite,
            )

            def rediscover() -> MediaMetadata:
                return self.discovery.discover(
                    source_id,
                    request.account_index,
                    timeouts=request.timeouts,
                    retries=request.retries,
                )

            return self.transfer.download(
                request,
                metadata,
                plan,
                rediscover=rediscover,
                progress=progress,
            )
        except GDriveVideoError as error:
            partial = plan.partial if plan and plan.partial.exists() else None
            try:
                completed = partial.stat().st_size if partial else 0
            except OSError:
                completed = 0
            recovery = None
            if partial is not None and source_id is not None:
                recovery = (
                    "Repeat the same authorized command with this file ID and output path; "
                    "supply a fresh Netscape cookie jar if access requires one."
                )
            return DownloadResult(
                kind=error.kind,
                message=redact_text(error.message),
                exit_code=error.exit_code,
                partial_path=partial,
                completed_bytes=completed,
                recovery=recovery,
            )
        except KeyboardInterrupt:
            return DownloadResult(
                kind=FailureKind.CANCELLED,
                message="Transfer cancelled.",
                exit_code=EXIT_CODES[FailureKind.CANCELLED],
            )
        except Exception:
            return DownloadResult(
                kind=FailureKind.INTERNAL,
                message="An unexpected internal error occurred; no credential details were logged.",
                exit_code=EXIT_CODES[FailureKind.INTERNAL],
                partial_path=plan.partial if plan and plan.partial.exists() else None,
            )
