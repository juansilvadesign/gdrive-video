"""Safe domain errors that never embed raw HTTP or credential details."""

from __future__ import annotations

from .models import EXIT_CODES, FailureKind


class GDriveVideoError(Exception):
    """Expected failure with a stable kind and a pre-redacted user message."""

    def __init__(
        self,
        kind: FailureKind,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.exit_code = EXIT_CODES[kind]
        self.retryable = retryable

    def __str__(self) -> str:
        return self.message


def invalid_input(message: str) -> GDriveVideoError:
    return GDriveVideoError(FailureKind.INVALID_INPUT, message)


def integrity_error(message: str) -> GDriveVideoError:
    return GDriveVideoError(FailureKind.INTEGRITY, message)
