"""Credential-safe Google Drive video transfer core."""

from .models import DownloadRequest, DownloadResult, ExitCode, FailureKind

__all__ = ["DownloadRequest", "DownloadResult", "ExitCode", "FailureKind"]

__version__ = "2.0"
