from __future__ import annotations

from pathlib import Path

import pytest
import requests
from conftest import SOURCE_ID
from test_transfer_integration import make_service, request_for

from gdrive_video import cli as cli_module
from gdrive_video.cli import (
    ProgressRenderer,
    _interactive_source,
    _render_result,
    build_parser,
    run,
)
from gdrive_video.cookies import CookieLoadReport
from gdrive_video.errors import GDriveVideoError
from gdrive_video.models import (
    DownloadRequest,
    DownloadResult,
    ExitCode,
    FailureKind,
    ProgressEvent,
    RetryPolicy,
    Timeouts,
)
from gdrive_video.service import DownloadService, validate_request


@pytest.mark.parametrize(
    ("mode", "kind"),
    [
        ("processing", FailureKind.PROCESSING),
        ("nonvideo", FailureKind.NON_VIDEO),
        ("conflicting-title", FailureKind.INTEGRITY),
        ("html", FailureKind.AUTHORIZATION),
    ],
)
def test_discovery_outcomes_from_local_fault_server(
    fault_server, tmp_path: Path, mode: str, kind: FailureKind
) -> None:
    service, metadata, media = make_service(fault_server, "/fresh", meta_mode=mode)
    try:
        result = service.execute(request_for(tmp_path / f"{mode}.mp4", attempts=1))
    finally:
        metadata.close()
        media.close()
    assert result.kind is kind


def test_missing_title_uses_nonempty_source_id_fallback(fault_server, tmp_path: Path) -> None:
    service, metadata, media = make_service(fault_server, "/fresh", meta_mode="missing-title")
    try:
        result = service.execute(
            DownloadRequest(
                source=SOURCE_ID,
                output=tmp_path,
                chunk_size=1024,
                timeouts=Timeouts(2, 2),
                retries=RetryPolicy(max_attempts=1),
            )
        )
    finally:
        metadata.close()
        media.close()
    assert result.ok
    assert result.final_path == tmp_path / f"drive-{SOURCE_ID}.mp4"


@pytest.mark.parametrize(
    ("status", "attempts", "kind"),
    [
        (401, 1, FailureKind.AUTHENTICATION),
        (403, 1, FailureKind.AUTHORIZATION),
        (418, 1, FailureKind.NETWORK),
        (429, 2, FailureKind.THROTTLED),
        (503, 2, FailureKind.NETWORK),
    ],
)
def test_metadata_http_statuses_are_stable_and_bounded(
    fault_server,
    tmp_path: Path,
    status: int,
    attempts: int,
    kind: FailureKind,
) -> None:
    delays: list[float] = []
    service, metadata, media = make_service(
        fault_server,
        "/fresh",
        sleep=delays.append,
        meta_status=status,
    )
    try:
        result = service.execute(
            request_for(tmp_path / f"metadata-{status}.mp4", attempts=attempts)
        )
    finally:
        metadata.close()
        media.close()
    assert result.kind is kind
    assert fault_server.state.counts["/metadata"] == attempts
    assert len(delays) == max(attempts - 1, 0)


class AlwaysTimeoutSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.timeouts: list[tuple[float, float]] = []

    def request(self, *args, **kwargs):
        self.timeouts.append(kwargs["timeout"])
        raise requests.ConnectTimeout("synthetic URL and token must not escape")


class StreamingTimeoutSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.closed_responses = 0

    def request(self, *args, **kwargs):
        self.calls += 1
        owner = self

        class Response:
            status_code = 200
            headers: dict[str, str] = {}

            def iter_content(self, _chunk_size):
                raise requests.ReadTimeout(
                    "https://drive.google.com/metadata?token=UNUSABLE_PRIVATE"
                )

            def close(self) -> None:
                owner.closed_responses += 1

        return Response()


def test_connect_timeout_is_separate_bounded_and_redacted(tmp_path: Path) -> None:
    metadata = AlwaysTimeoutSession()
    media = requests.Session()
    delays: list[float] = []
    service = DownloadService(metadata, media, sleep=delays.append)
    result = service.execute(
        DownloadRequest(
            source=SOURCE_ID,
            output=tmp_path / "timeout.mp4",
            timeouts=Timeouts(3, 17),
            retries=RetryPolicy(max_attempts=3, base_delay=1, maximum_delay=10),
        )
    )
    metadata.close()
    media.close()
    assert result.kind is FailureKind.NETWORK
    assert metadata.timeouts == [(3, 17), (3, 17), (3, 17)]
    assert delays == [1, 2]
    assert "token" not in result.message


def test_metadata_stream_timeout_is_retried_closed_and_redacted(tmp_path: Path) -> None:
    metadata = StreamingTimeoutSession()
    media = requests.Session()
    delays: list[float] = []
    service = DownloadService(metadata, media, sleep=delays.append)
    result = service.execute(
        DownloadRequest(
            source=SOURCE_ID,
            output=tmp_path / "metadata-stream-timeout.mp4",
            retries=RetryPolicy(max_attempts=2, base_delay=1, maximum_delay=10),
        )
    )
    metadata.close()
    media.close()

    assert result.kind is FailureKind.NETWORK
    assert metadata.calls == 2
    assert metadata.closed_responses == 2
    assert delays == [1]
    assert "UNUSABLE_PRIVATE" not in result.message
    assert not (tmp_path / "metadata-stream-timeout.mp4").exists()


@pytest.mark.parametrize(
    "download_request",
    [
        DownloadRequest(source=SOURCE_ID, account_index=-1),
        DownloadRequest(source=SOURCE_ID, account_index=True),
        DownloadRequest(source=SOURCE_ID, timeouts=Timeouts(0, 1)),
        DownloadRequest(source=SOURCE_ID, timeouts=Timeouts(1, 4000)),
        DownloadRequest(source=SOURCE_ID, retries=RetryPolicy(max_attempts=0)),
        DownloadRequest(source=SOURCE_ID, retries=RetryPolicy(max_attempts=6)),
        DownloadRequest(
            source=SOURCE_ID,
            retries=RetryPolicy(max_attempts=1, base_delay=-1),
        ),
        DownloadRequest(source=SOURCE_ID, expected_sha256="not-a-digest"),
    ],
)
def test_request_contract_rejects_invalid_non_io_configuration(
    download_request: DownloadRequest,
) -> None:
    with pytest.raises(GDriveVideoError):
        validate_request(download_request)


@pytest.mark.parametrize(
    ("raised", "kind"),
    [
        (RuntimeError("synthetic"), FailureKind.INTERNAL),
        (KeyboardInterrupt(), FailureKind.CANCELLED),
    ],
)
def test_service_converts_unexpected_and_keyboard_interrupt_to_typed_results(
    raised: BaseException, kind: FailureKind
) -> None:
    metadata = requests.Session()
    media = requests.Session()
    service = DownloadService(metadata, media)

    def fail(*_args, **_kwargs):
        raise raised

    service.discovery.discover = fail
    try:
        result = service.execute(DownloadRequest(source=SOURCE_ID))
    finally:
        metadata.close()
        media.close()
    assert result.kind is kind
    assert "synthetic" not in result.message


def test_media_read_timeout_uses_same_separate_tuple_and_preserves_no_final(
    fault_server, tmp_path: Path, monkeypatch
) -> None:
    service, metadata, media = make_service(fault_server, "/fresh", sleep=lambda _delay: None)
    seen: list[tuple[float, float]] = []

    def read_timeout(*_args, **kwargs):
        seen.append(kwargs["timeout"])
        raise requests.ReadTimeout("synthetic signed URL query")

    monkeypatch.setattr(media, "request", read_timeout)
    try:
        result = service.execute(
            DownloadRequest(
                source=SOURCE_ID,
                output=tmp_path / "read-timeout.mp4",
                timeouts=Timeouts(4, 19),
                retries=RetryPolicy(max_attempts=2, base_delay=0),
            )
        )
    finally:
        metadata.close()
        media.close()
    assert result.kind is FailureKind.NETWORK
    assert seen == [(4, 19), (4, 19)]
    assert not (tmp_path / "read-timeout.mp4").exists()


def test_permission_denied_is_a_filesystem_outcome(
    fault_server, tmp_path: Path, monkeypatch
) -> None:
    def denied(*_args, **_kwargs):
        raise GDriveVideoError(
            FailureKind.FILESYSTEM, "The partial output could not be opened safely."
        )

    monkeypatch.setattr("gdrive_video.transfer._open_partial", denied)
    service, metadata, media = make_service(fault_server, "/fresh")
    try:
        result = service.execute(request_for(tmp_path / "denied.mp4", attempts=1))
    finally:
        metadata.close()
        media.close()
    assert result.kind is FailureKind.FILESYSTEM
    assert not (tmp_path / "denied.mp4").exists()


def test_media_404_is_authorization_not_false_success(fault_server, tmp_path: Path) -> None:
    service, metadata, media = make_service(fault_server, "/status404")
    try:
        result = service.execute(request_for(tmp_path / "missing.mp4", attempts=1))
    finally:
        metadata.close()
        media.close()
    assert result.kind is FailureKind.AUTHORIZATION


def test_cli_raw_cookie_failure_never_prints_path_or_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cookie_path = tmp_path / "private-account-cookies.txt"
    cookie_path.write_text("Cookie: SID=UNUSABLE_PRIVATE_VALUE\n", encoding="utf-8")
    cookie_path.chmod(0o600)
    code = run([SOURCE_ID, "--cookies-file", str(cookie_path)])
    captured = capsys.readouterr()
    rendered = captured.out + captured.err
    assert code == 3
    assert str(cookie_path) not in rendered
    assert "UNUSABLE_PRIVATE_VALUE" not in rendered
    assert "temporary login credentials" in rendered
    assert "Netscape" in rendered


def test_cli_help_and_parser_use_authorized_not_bypass_language(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(["--help"])
    assert caught.value.code == 0
    help_text = capsys.readouterr().out.lower()
    assert "authorized" in help_text
    assert "bypass" not in help_text
    assert "protected" not in help_text


def test_cli_invalid_chunk_has_stable_exit_code_without_network(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run([SOURCE_ID, "--chunk-size", "1"]) == 2
    assert "invalid_input" in capsys.readouterr().out


def test_cli_result_output_does_not_disclose_discovered_title_or_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_marker = "UNUSABLE_PRIVATE_TITLE"
    result = DownloadResult(
        kind=FailureKind.SUCCESS,
        message="Download completed.",
        exit_code=ExitCode.SUCCESS,
        final_path=tmp_path / f"{private_marker}.mp4",
        completed_bytes=10,
    )
    _render_result(result, verbose=False)
    assert private_marker not in capsys.readouterr().out


def test_cli_renderer_updates_indeterminate_total_and_closes(monkeypatch) -> None:
    created: list[object] = []

    class FakeBar:
        def __init__(self, **kwargs) -> None:
            self.total = kwargs["total"]
            self.n = kwargs["initial"]
            self.updates: list[int] = []
            self.closed = False
            created.append(self)

        def update(self, amount: int) -> None:
            self.updates.append(amount)
            self.n += amount

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(cli_module, "tqdm", FakeBar)
    renderer = ProgressRenderer()
    renderer(ProgressEvent(5, None))
    renderer(ProgressEvent(8, 10))
    renderer(ProgressEvent(10, 10, "complete"))
    bar = created[0]
    assert bar.total == 10
    assert bar.updates == [3, 2]
    assert bar.closed is True
    assert renderer.bar is None


def test_cli_interactive_source_is_stripped(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: f"  {SOURCE_ID}  ")
    assert _interactive_source() == SOURCE_ID
    assert "authorized" in capsys.readouterr().out


def test_cli_success_path_closes_sessions_and_renders_verbose_report(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    class TrackingSession(requests.Session):
        def __init__(self) -> None:
            super().__init__()
            self.was_closed = False

        def close(self) -> None:
            self.was_closed = True
            super().close()

    metadata = TrackingSession()
    media = TrackingSession()
    report = CookieLoadReport(loaded=2, expired=1, ignored=3)

    def fake_sessions(_cookie_file):
        return metadata, media, report

    class FakeService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def execute(self, _request, *, progress=None) -> DownloadResult:
            return DownloadResult(
                kind=FailureKind.SUCCESS,
                message="Synthetic completion.",
                exit_code=ExitCode.SUCCESS,
                final_path=tmp_path / "UNUSABLE_PRIVATE_TITLE.mp4",
                completed_bytes=10,
                sha256="a" * 64,
            )

    monkeypatch.setattr(cli_module, "create_sessions", fake_sessions)
    monkeypatch.setattr(cli_module, "DownloadService", FakeService)
    code = run(
        [
            SOURCE_ID,
            "--cookies-file",
            str(tmp_path / "not-read.txt"),
            "--verbose",
            "--sha256",
            "a" * 64,
        ]
    )
    rendered = capsys.readouterr().out
    assert code == 0
    assert metadata.was_closed and media.was_closed
    assert "Loaded 2" in rendered
    assert "SHA-256" in rendered
    assert "UNUSABLE_PRIVATE_TITLE" not in rendered


def test_result_renderer_covers_partial_and_recovery_without_path(capsys) -> None:
    result = DownloadResult(
        kind=FailureKind.NETWORK,
        message="Synthetic network stop.",
        exit_code=ExitCode.NETWORK,
        partial_path=Path("UNUSABLE_PRIVATE_TITLE.mp4.part"),
        completed_bytes=7,
        recovery="Repeat the same command.",
    )
    _render_result(result, verbose=False)
    rendered = capsys.readouterr().out
    assert "ERROR [network]" in rendered
    assert "7 bytes" in rendered
    assert "Recovery:" in rendered
    assert "UNUSABLE_PRIVATE_TITLE" not in rendered
