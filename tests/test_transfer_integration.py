from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import requests
from conftest import ETAG, LAST_MODIFIED, MEDIA_BYTES, SOURCE_ID

from gdrive_video.files import SIDECAR_SCHEMA, OutputPlan, ResumeState, write_resume_state
from gdrive_video.models import DownloadRequest, FailureKind, RetryPolicy, Timeouts
from gdrive_video.security import UrlPolicy
from gdrive_video.service import DownloadService


def make_service(
    fault_server,
    media: str,
    *,
    sleep=None,
    meta_mode: str = "ok",
    meta_status: int = 200,
):
    metadata_session = requests.Session()
    media_session = requests.Session()
    policy = UrlPolicy(test_origins=frozenset({fault_server.origin}))
    service = DownloadService(
        metadata_session,
        media_session,
        policy=policy,
        endpoint_template=fault_server.endpoint_template(
            media, meta_mode=meta_mode, meta_status=meta_status
        ),
        sleep=sleep,
    )
    return service, metadata_session, media_session


def request_for(
    output: Path,
    *,
    attempts: int = 3,
    expected_sha256: str | None = None,
    overwrite: bool = False,
    restart: bool = False,
) -> DownloadRequest:
    return DownloadRequest(
        source=SOURCE_ID,
        output=output,
        chunk_size=1024,
        expected_sha256=expected_sha256,
        overwrite=overwrite,
        restart=restart,
        timeouts=Timeouts(2, 2),
        retries=RetryPolicy(max_attempts=attempts, base_delay=0, maximum_delay=3),
    )


def execute(fault_server, media: str, request: DownloadRequest, *, sleep=None, progress=None):
    service, metadata_session, media_session = make_service(fault_server, media, sleep=sleep)
    try:
        return service.execute(request, progress=progress)
    finally:
        metadata_session.close()
        media_session.close()


def seed_partial(
    final: Path, data: bytes, *, total: int | None = None, etag: str | None = ETAG
) -> None:
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(data)
    write_resume_state(
        plan.sidecar,
        ResumeState(
            schema_version=SIDECAR_SCHEMA,
            source_id=SOURCE_ID,
            expected_total=len(MEDIA_BYTES) if total is None else total,
            etag=etag,
            last_modified=LAST_MODIFIED if etag is not None else None,
            content_type="video/mp4",
            expected_sha256=None,
            completed_bytes=len(data),
        ),
    )


def assert_preserved(final: Path, expected: bytes) -> None:
    assert not final.exists()
    assert Path(f"{final}.part").read_bytes() == expected
    assert Path(f"{final}.part.json").exists()


def test_fresh_download_is_byte_identical_hashed_and_atomically_promoted(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "fresh.mp4"
    result = execute(fault_server, "/fresh", request_for(final))
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES
    assert result.sha256 == hashlib.sha256(MEDIA_BYTES).hexdigest()
    assert not Path(f"{final}.part").exists()
    assert not Path(f"{final}.part.json").exists()


def test_expected_digest_accepts_uppercase_hex_from_typed_callers(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "uppercase-digest.mp4"
    expected = hashlib.sha256(MEDIA_BYTES).hexdigest().upper()
    result = execute(
        fault_server,
        "/fresh",
        request_for(final, expected_sha256=expected),
    )
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES


def test_unknown_length_streams_to_clean_eof(fault_server, tmp_path: Path) -> None:
    final = tmp_path / "unknown.mp4"
    totals: list[int | None] = []
    result = execute(
        fault_server,
        "/unknown",
        request_for(final),
        progress=lambda event: totals.append(event.total_bytes),
    )
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES
    assert None in totals


def test_partial_disconnect_rediscovery_resumes_with_range_and_if_range(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "disconnect.mp4"
    result = execute(fault_server, "/disconnect", request_for(final))
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES
    media_requests = [item for item in fault_server.state.requests if item["path"] == "/disconnect"]
    assert len(media_requests) == 2
    assert media_requests[0]["range"] is None
    assert media_requests[1]["range"] == "bytes=4096-"
    assert media_requests[1]["if_range"] == ETAG


def test_stalled_body_hits_idle_read_timeout_and_never_promotes(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "stalled.mp4"
    request = request_for(final, attempts=1)
    request = DownloadRequest(
        source=request.source,
        output=request.output,
        chunk_size=request.chunk_size,
        timeouts=Timeouts(1, 0.05),
        retries=request.retries,
    )

    result = execute(fault_server, "/stall", request)

    assert result.kind is FailureKind.NETWORK
    assert not final.exists()
    assert Path(f"{final}.part").exists()
    assert Path(f"{final}.part.json").exists()


def test_valid_resume_produces_exact_fixture(fault_server, tmp_path: Path) -> None:
    final = tmp_path / "resume.mp4"
    prefix = MEDIA_BYTES[:8192]
    seed_partial(final, prefix)
    result = execute(fault_server, "/fresh", request_for(final))
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES
    request = next(item for item in fault_server.state.requests if item["path"] == "/fresh")
    assert request["range"] == "bytes=8192-"
    assert request["if_range"] == ETAG


@pytest.mark.parametrize(
    ("media", "message"),
    [
        ("/ignore-range", "ignored"),
        ("/wrong-start", "begin"),
        ("/wrong-total", "total"),
        ("/changed-etag", "ETag"),
    ],
)
def test_invalid_resume_responses_never_append_or_promote(
    fault_server, tmp_path: Path, media: str, message: str
) -> None:
    final = tmp_path / f"{media.removeprefix('/')}.mp4"
    prefix = MEDIA_BYTES[:4096]
    seed_partial(final, prefix)
    result = execute(fault_server, media, request_for(final))
    assert result.kind is FailureKind.INTEGRITY
    assert message.lower() in result.message.lower()
    assert_preserved(final, prefix)


def test_valid_416_requires_complete_matching_identity(fault_server, tmp_path: Path) -> None:
    final = tmp_path / "complete.mp4"
    seed_partial(final, MEDIA_BYTES)
    result = execute(fault_server, "/fresh", request_for(final))
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES


def test_invalid_416_never_promotes(fault_server, tmp_path: Path) -> None:
    final = tmp_path / "invalid416.mp4"
    prefix = MEDIA_BYTES[:4096]
    seed_partial(final, prefix)
    result = execute(fault_server, "/invalid416", request_for(final))
    assert result.kind is FailureKind.INTEGRITY
    assert_preserved(final, prefix)


def test_unknown_length_partial_without_validator_requires_explicit_restart(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "unsafe-unknown.mp4"
    seed_partial(final, MEDIA_BYTES[:1024], total=None, etag=None)
    # Explicitly make the stored total unknown; seed_partial's default None means fixture total.
    sidecar = Path(f"{final}.part.json")
    payload = __import__("json").loads(sidecar.read_text())
    payload["expected_total"] = None
    sidecar.write_text(__import__("json").dumps(payload), encoding="utf-8")
    result = execute(fault_server, "/unknown", request_for(final))
    assert result.kind is FailureKind.CONFLICT
    assert "cannot be resumed safely" in result.message
    assert_preserved(final, MEDIA_BYTES[:1024])


@pytest.mark.parametrize("media", ["/html", "/json", "/empty", "/encoded"])
def test_non_media_empty_and_encoded_bodies_never_promote(
    fault_server, tmp_path: Path, media: str
) -> None:
    final = tmp_path / f"{media.removeprefix('/')}.mp4"
    result = execute(fault_server, media, request_for(final, attempts=1))
    assert not result.ok
    assert not final.exists()


def test_known_redirect_succeeds_and_unknown_or_excessive_redirects_fail(
    fault_server, tmp_path: Path
) -> None:
    known = execute(fault_server, "/redirect-known", request_for(tmp_path / "known.mp4"))
    assert known.ok
    assert (tmp_path / "known.mp4").read_bytes() == MEDIA_BYTES

    unknown = execute(
        fault_server,
        "/redirect-unknown",
        request_for(tmp_path / "unknown-host.mp4", attempts=1),
    )
    assert unknown.kind is FailureKind.INTEGRITY

    loop = execute(
        fault_server,
        "/redirect-loop",
        request_for(tmp_path / "loop.mp4", attempts=1),
    )
    assert loop.kind is FailureKind.INTEGRITY


def test_retry_after_and_transient_statuses_are_bounded_without_real_sleep(
    fault_server, tmp_path: Path
) -> None:
    delays: list[float] = []
    throttled = execute(
        fault_server,
        "/retry429",
        request_for(tmp_path / "retry429.mp4"),
        sleep=delays.append,
    )
    assert throttled.ok
    assert delays == [2.0, 2.0]
    assert fault_server.state.counts["/retry429"] == 3

    delays.clear()
    transient = execute(
        fault_server,
        "/retry500",
        request_for(tmp_path / "retry500.mp4"),
        sleep=delays.append,
    )
    assert transient.ok
    assert delays == [0, 0]
    assert fault_server.state.counts["/retry500"] == 3


def test_expired_media_url_is_rediscovered_but_bounded(fault_server, tmp_path: Path) -> None:
    result = execute(
        fault_server,
        "/status403",
        request_for(tmp_path / "expired.mp4"),
        sleep=lambda _delay: None,
    )
    assert result.kind is FailureKind.EXPIRED_URL
    assert fault_server.state.counts["/status403"] == 3
    assert fault_server.state.counts["/metadata"] == 3


def test_optional_digest_mismatch_preserves_complete_partial(fault_server, tmp_path: Path) -> None:
    final = tmp_path / "digest.mp4"
    result = execute(
        fault_server,
        "/fresh",
        request_for(final, expected_sha256="0" * 64),
    )
    assert result.kind is FailureKind.INTEGRITY
    assert_preserved(final, MEDIA_BYTES)


def test_existing_final_conflicts_before_media_transfer_and_overwrite_is_explicit(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "existing.mp4"
    final.write_bytes(b"old")
    conflict = execute(fault_server, "/fresh", request_for(final))
    assert conflict.kind is FailureKind.CONFLICT
    assert final.read_bytes() == b"old"
    assert fault_server.state.counts["/fresh"] == 0

    replaced = execute(fault_server, "/fresh", request_for(final, overwrite=True))
    assert replaced.ok
    assert final.read_bytes() == MEDIA_BYTES


def test_restart_archives_existing_partial_then_starts_fresh(fault_server, tmp_path: Path) -> None:
    final = tmp_path / "restart.mp4"
    prefix = MEDIA_BYTES[:1024]
    seed_partial(final, prefix)
    result = execute(fault_server, "/ignore-range", request_for(final, restart=True))
    assert result.ok
    assert final.read_bytes() == MEDIA_BYTES
    stale = list(tmp_path.glob("restart.mp4.part*.stale.*"))
    assert len(stale) == 2
    assert any(path.read_bytes() == prefix for path in stale if ".json." not in path.name)


def test_cancellation_preserves_consistent_partial_and_sidecar(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "cancelled.mp4"

    def cancel(_event) -> None:
        raise KeyboardInterrupt

    result = execute(fault_server, "/fresh", request_for(final), progress=cancel)
    assert result.kind is FailureKind.CANCELLED
    part = Path(f"{final}.part")
    assert 0 < part.stat().st_size < len(MEDIA_BYTES)
    assert Path(f"{final}.part.json").exists()
    assert not final.exists()


def test_atomic_promotion_failure_keeps_full_partial(
    fault_server, tmp_path: Path, monkeypatch
) -> None:
    final = tmp_path / "rename-failure.mp4"

    def fail_link(*_args, **_kwargs):
        raise OSError("synthetic unsupported atomic link")

    monkeypatch.setattr("gdrive_video.files.os.link", fail_link)
    result = execute(fault_server, "/fresh", request_for(final))
    assert result.kind is FailureKind.FILESYSTEM
    assert_preserved(final, MEDIA_BYTES)


def test_disk_full_write_failure_preserves_sidecar_and_no_final(
    fault_server, tmp_path: Path, monkeypatch
) -> None:
    from gdrive_video import transfer as transfer_module

    final = tmp_path / "disk-full.mp4"
    real_open = transfer_module._open_partial

    class DiskFullHandle:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def write(self, _chunk: bytes) -> int:
            raise OSError(28, "synthetic disk full")

        def flush(self) -> None:
            self.wrapped.flush()

        def fileno(self) -> int:
            return self.wrapped.fileno()

        def close(self) -> None:
            self.wrapped.close()

    def disk_full_open(path: Path, *, offset: int):
        return DiskFullHandle(real_open(path, offset=offset))

    monkeypatch.setattr(transfer_module, "_open_partial", disk_full_open)
    result = execute(fault_server, "/fresh", request_for(final, attempts=1))
    assert result.kind is FailureKind.FILESYSTEM
    assert not final.exists()
    assert Path(f"{final}.part").exists()
    assert Path(f"{final}.part.json").exists()


def test_invalid_chunk_is_rejected_before_network_or_output_mutation(
    fault_server, tmp_path: Path
) -> None:
    final = tmp_path / "invalid.mp4"
    request = DownloadRequest(source=SOURCE_ID, output=final, chunk_size=0)
    result = execute(fault_server, "/fresh", request)
    assert result.kind is FailureKind.INVALID_INPUT
    assert fault_server.state.requests == []
    assert not final.exists()
