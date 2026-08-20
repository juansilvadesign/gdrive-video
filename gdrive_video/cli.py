"""Thin command-line adapter for the typed transfer service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from . import __version__
from .cookies import create_sessions
from .errors import GDriveVideoError
from .models import DownloadRequest, DownloadResult, ProgressEvent, RetryPolicy, Timeouts
from .service import DownloadService, validate_request


class ProgressRenderer:
    def __init__(self) -> None:
        self.bar: tqdm | None = None

    def __call__(self, event: ProgressEvent) -> None:
        if self.bar is None:
            self.bar = tqdm(
                total=event.total_bytes,
                initial=event.completed_bytes,
                unit="B",
                unit_scale=True,
                desc="Downloading",
            )
            return
        if event.total_bytes is not None and self.bar.total != event.total_bytes:
            self.bar.total = event.total_bytes
        delta = event.completed_bytes - int(self.bar.n)
        if delta > 0:
            self.bar.update(delta)
        if event.phase == "complete":
            self.close()

    def close(self) -> None:
        if self.bar is not None:
            self.bar.close()
            self.bar = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download one Google Drive video that you are already authorized to access and save."
        )
    )
    parser.add_argument("source", nargs="?", help="Drive file ID or supported HTTPS Drive file URL")
    parser.add_argument(
        "-o", "--output", type=Path, help="Final filename or an existing output directory"
    )
    parser.add_argument(
        "-c",
        "--chunk-size",
        type=int,
        default=64 * 1024,
        help="Transfer chunk bytes (1024 through 8388608; default: 65536)",
    )
    parser.add_argument(
        "--cookies-file", type=Path, help="Private mode-0600 Netscape cookies.txt export"
    )
    parser.add_argument(
        "--account-index", type=int, default=0, help="Drive account slot from 0 through 99"
    )
    parser.add_argument(
        "--connect-timeout", type=float, default=10.0, help="Connection timeout seconds"
    )
    parser.add_argument(
        "--read-timeout", type=float, default=60.0, help="Idle read timeout seconds"
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="Total bounded attempts (1 through 5)"
    )
    parser.add_argument("--sha256", help="Optional expected SHA-256 digest")
    parser.add_argument(
        "--overwrite", action="store_true", help="Atomically replace an existing regular final file"
    )
    parser.add_argument(
        "--restart", action="store_true", help="Archive existing partial state and start fresh"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show credential-safe lifecycle details"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _interactive_source() -> str:
    print("GDrive Video — authorized single-file transfer")
    return input("Google Drive file URL or ID: ").strip()


def _render_result(result: DownloadResult, *, verbose: bool) -> None:
    prefix = "OK" if result.ok else "ERROR"
    print(f"{prefix} [{result.kind.value}]: {result.message}")
    if result.final_path is not None:
        print("Final file created in the selected output location.")
        print(f"Bytes: {result.completed_bytes}")
        if verbose and result.sha256:
            print(f"SHA-256: {result.sha256}")
    elif result.partial_path is not None:
        print(f"Partial and resume state preserved ({result.completed_bytes} bytes).")
    if result.recovery:
        print(f"Recovery: {result.recovery}")


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = args.source or _interactive_source()
    if args.cookies_file:
        print(
            "WARNING: Exported browser cookies are temporary login credentials. "
            "Use a disposable/test account where possible, keep the file private, "
            "and delete it manually after it expires or the transfer finishes.",
            file=sys.stderr,
        )

    request = DownloadRequest(
        source=source,
        output=args.output,
        chunk_size=args.chunk_size,
        overwrite=args.overwrite,
        restart=args.restart,
        expected_sha256=args.sha256.lower() if args.sha256 else None,
        account_index=args.account_index,
        timeouts=Timeouts(args.connect_timeout, args.read_timeout),
        retries=RetryPolicy(max_attempts=args.retries),
    )
    metadata_session = None
    media_session = None
    renderer = ProgressRenderer()
    try:
        validate_request(request)
        metadata_session, media_session, report = create_sessions(args.cookies_file)
        if args.verbose:
            print("Validated input and isolated metadata/media HTTP sessions.")
            if report:
                print(
                    f"Loaded {report.loaded} eligible unexpired cookies for the exact "
                    "Drive metadata host; "
                    f"ignored {report.ignored} unrelated and {report.expired} expired entries."
                )
        service = DownloadService(
            metadata_session,
            media_session,
            credentials_supplied=args.cookies_file is not None,
        )
        result = service.execute(request, progress=renderer)
    except GDriveVideoError as error:
        result = DownloadResult(
            kind=error.kind,
            message=error.message,
            exit_code=error.exit_code,
        )
    finally:
        renderer.close()
        if metadata_session is not None:
            metadata_session.close()
        if media_session is not None:
            media_session.close()
    _render_result(result, verbose=args.verbose)
    return int(result.exit_code)
