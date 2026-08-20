"""Typed public contracts used by the CLI and future local adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path


class ExitCode(IntEnum):
    """Stable process exit codes documented in the transfer contract."""

    SUCCESS = 0
    INVALID_INPUT = 2
    AUTHENTICATION = 3
    AUTHORIZATION = 4
    PROCESSING = 5
    NON_VIDEO = 6
    EXPIRED_URL = 7
    THROTTLED = 8
    NETWORK = 9
    FILESYSTEM = 10
    CONFLICT = 11
    INTEGRITY = 12
    INTERNAL = 70
    CANCELLED = 130


class FailureKind(str, Enum):
    """Machine-readable result kinds; messages remain safe for users and logs."""

    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    PROCESSING = "processing"
    NON_VIDEO = "non_video"
    EXPIRED_URL = "expired_url"
    THROTTLED = "throttled"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    CONFLICT = "conflict"
    INTEGRITY = "integrity"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


EXIT_CODES: dict[FailureKind, ExitCode] = {
    FailureKind.SUCCESS: ExitCode.SUCCESS,
    FailureKind.INVALID_INPUT: ExitCode.INVALID_INPUT,
    FailureKind.AUTHENTICATION: ExitCode.AUTHENTICATION,
    FailureKind.AUTHORIZATION: ExitCode.AUTHORIZATION,
    FailureKind.PROCESSING: ExitCode.PROCESSING,
    FailureKind.NON_VIDEO: ExitCode.NON_VIDEO,
    FailureKind.EXPIRED_URL: ExitCode.EXPIRED_URL,
    FailureKind.THROTTLED: ExitCode.THROTTLED,
    FailureKind.NETWORK: ExitCode.NETWORK,
    FailureKind.FILESYSTEM: ExitCode.FILESYSTEM,
    FailureKind.CONFLICT: ExitCode.CONFLICT,
    FailureKind.INTEGRITY: ExitCode.INTEGRITY,
    FailureKind.CANCELLED: ExitCode.CANCELLED,
    FailureKind.INTERNAL: ExitCode.INTERNAL,
}


@dataclass(frozen=True, slots=True)
class Timeouts:
    """Separate connect and idle-read timeout values in seconds."""

    connect: float = 10.0
    read: float = 60.0

    def as_requests_tuple(self) -> tuple[float, float]:
        return (self.connect, self.read)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry behavior for discovery and media requests."""

    max_attempts: int = 3
    base_delay: float = 0.5
    maximum_delay: float = 30.0


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    """One authorized transfer request, independent from any user interface."""

    source: str
    output: Path | None = None
    chunk_size: int = 64 * 1024
    overwrite: bool = False
    restart: bool = False
    expected_sha256: str | None = None
    account_index: int = 0
    timeouts: Timeouts = field(default_factory=Timeouts)
    retries: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """A renderer-neutral transfer progress update."""

    completed_bytes: int
    total_bytes: int | None
    phase: str = "transferring"


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Short-lived discovery output. The signed URL is deliberately repr-hidden."""

    source_id: str
    playback_url: str = field(repr=False)
    title: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Stable result returned to CLI/GUI adapters; contains no credentials."""

    kind: FailureKind
    message: str
    exit_code: ExitCode
    final_path: Path | None = None
    partial_path: Path | None = None
    completed_bytes: int = 0
    sha256: str | None = None
    recovery: str | None = None

    @property
    def ok(self) -> bool:
        return self.kind is FailureKind.SUCCESS
