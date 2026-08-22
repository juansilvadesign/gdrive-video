from __future__ import annotations

from datetime import datetime, timezone

import pytest
import requests
from conftest import ETAG, LAST_MODIFIED, SOURCE_ID

from gdrive_video.errors import GDriveVideoError
from gdrive_video.files import SIDECAR_SCHEMA, ResumeState
from gdrive_video.http import retry_delay
from gdrive_video.transfer import _if_range, _validate_416, _validate_response


def response(status: int, **headers: str) -> requests.Response:
    item = requests.Response()
    item.status_code = status
    item.headers.update(headers)
    return item


def resume_state(**changes) -> ResumeState:
    values = {
        "schema_version": SIDECAR_SCHEMA,
        "source_id": SOURCE_ID,
        "expected_total": 10,
        "etag": ETAG,
        "last_modified": LAST_MODIFIED,
        "content_type": "video/mp4",
        "expected_sha256": None,
        "completed_bytes": 5,
    }
    values.update(changes)
    return ResumeState(**values)


@pytest.mark.parametrize(
    ("header", "attempt", "base", "maximum", "expected"),
    [
        (None, 3, 1.0, 3.0, 3.0),
        ("10", 1, 1.0, 4.0, 4.0),
        ("-2", 1, 1.0, 4.0, 0.0),
        ("not-a-date", 2, 1.0, 10.0, 2.0),
    ],
)
def test_retry_delay_is_bounded_and_has_deterministic_fallback(
    header: str | None, attempt: int, base: float, maximum: float, expected: float
) -> None:
    assert (
        retry_delay(
            header,
            attempt=attempt,
            base_delay=base,
            maximum_delay=maximum,
        )
        == expected
    )


def test_retry_delay_parses_http_date_against_injected_clock() -> None:
    now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    assert (
        retry_delay(
            "Thu, 20 Aug 2026 12:00:12 GMT",
            attempt=1,
            base_delay=1,
            maximum_delay=30,
            now=now,
        )
        == 12
    )


@pytest.mark.parametrize(
    ("item", "offset", "state", "hint", "message"),
    [
        (
            response(200, **{"Content-Type": "video/mp4", "Content-Length": "bad"}),
            0,
            None,
            None,
            "Content-Length",
        ),
        (
            response(200, **{"Content-Type": "video/mp4", "Content-Encoding": "gzip"}),
            0,
            None,
            None,
            "encoded",
        ),
        (
            response(200, **{"Content-Type": "video/mp4", "ETag": "bad\nvalidator"}),
            0,
            None,
            None,
            "invalid ETag",
        ),
        (
            response(
                200,
                **{"Content-Type": "video/mp4", "Last-Modified": "x" * 1025},
            ),
            0,
            None,
            None,
            "invalid Last-Modified",
        ),
        (response(200, **{"Content-Type": "text/html"}), 0, None, None, "content type"),
        (response(206, **{"Content-Type": "video/mp4"}), 0, None, None, "required 200"),
        (response(200, **{"Content-Type": "video/mp4"}), 5, resume_state(), None, "ignored"),
        (response(418, **{"Content-Type": "video/mp4"}), 5, resume_state(), None, "required 206"),
        (
            response(206, **{"Content-Type": "video/mp4", "Content-Range": "malformed"}),
            5,
            resume_state(),
            None,
            "malformed",
        ),
        (
            response(206, **{"Content-Type": "video/mp4", "Content-Range": "bytes 4-9/10"}),
            5,
            resume_state(),
            None,
            "local byte",
        ),
        (
            response(206, **{"Content-Type": "video/mp4", "Content-Range": "bytes 5-4/10"}),
            5,
            resume_state(),
            None,
            "local byte",
        ),
        (
            response(206, **{"Content-Type": "video/mp4", "Content-Range": "bytes 5-10/10"}),
            5,
            resume_state(),
            None,
            "impossible",
        ),
        (
            response(
                206,
                **{
                    "Content-Type": "video/mp4",
                    "Content-Range": "bytes 5-9/10",
                    "Content-Length": "4",
                },
            ),
            5,
            resume_state(),
            None,
            "did not match",
        ),
        (
            response(
                206,
                **{
                    "Content-Type": "video/mp4",
                    "Content-Range": "bytes 5-9/11",
                    "Content-Length": "5",
                    "ETag": ETAG,
                    "Last-Modified": LAST_MODIFIED,
                },
            ),
            5,
            resume_state(),
            None,
            "total changed",
        ),
        (
            response(
                206,
                **{
                    "Content-Type": "video/mp4",
                    "Content-Range": "bytes 5-9/10",
                    "Content-Length": "5",
                    "Last-Modified": LAST_MODIFIED,
                },
            ),
            5,
            resume_state(),
            None,
            "ETag",
        ),
        (
            response(
                206,
                **{
                    "Content-Type": "video/mp4",
                    "Content-Range": "bytes 5-9/10",
                    "Content-Length": "5",
                    "ETag": ETAG,
                },
            ),
            5,
            resume_state(),
            None,
            "Last-Modified",
        ),
        (
            response(
                206,
                **{
                    "Content-Type": "video/webm",
                    "Content-Range": "bytes 5-9/10",
                    "Content-Length": "5",
                    "ETag": ETAG,
                    "Last-Modified": LAST_MODIFIED,
                },
            ),
            5,
            resume_state(),
            None,
            "content type changed",
        ),
    ],
)
def test_response_contract_rejects_malformed_or_changed_identity(
    item: requests.Response,
    offset: int,
    state: ResumeState | None,
    hint: str | None,
    message: str,
) -> None:
    with pytest.raises(GDriveVideoError, match=message):
        _validate_response(item, offset=offset, state=state, hinted_content_type=hint)


def test_octet_stream_is_accepted_only_with_video_hint() -> None:
    item = response(
        200,
        **{"Content-Type": "application/octet-stream", "Content-Length": "3"},
    )
    identity = _validate_response(
        item,
        offset=0,
        state=None,
        hinted_content_type="video/webm; codecs=vp9",
    )
    assert identity.content_type == "video/webm"
    assert identity.total == 3


def test_if_range_prefers_strong_etag_then_last_modified() -> None:
    assert _if_range(resume_state()) == ETAG
    assert _if_range(resume_state(etag='W/"weak"')) == LAST_MODIFIED
    assert _if_range(resume_state(etag=None, last_modified=None)) is None


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (response(416), "valid remote total"),
        (
            response(
                416,
                **{
                    "Content-Range": "bytes */10",
                    "ETag": '"changed"',
                    "Last-Modified": LAST_MODIFIED,
                },
            ),
            "ETag",
        ),
        (
            response(
                416,
                **{"Content-Range": "bytes */10", "ETag": ETAG},
            ),
            "Last-Modified",
        ),
        (
            response(
                416,
                **{
                    "Content-Range": "bytes */99",
                    "ETag": ETAG,
                    "Last-Modified": LAST_MODIFIED,
                },
            ),
            "partial and sidecar",
        ),
    ],
)
def test_416_requires_complete_identity(item: requests.Response, message: str) -> None:
    with pytest.raises(GDriveVideoError, match=message):
        _validate_416(item, resume_state(completed_bytes=10), 10)


def test_416_total_must_match_the_sidecar_not_only_the_partial() -> None:
    """A 416 total that agrees with the local partial but not the recorded total is refused."""
    item = response(
        416,
        **{"Content-Range": "bytes */10", "ETag": ETAG, "Last-Modified": LAST_MODIFIED},
    )
    with pytest.raises(GDriveVideoError, match="partial and sidecar"):
        _validate_416(item, resume_state(expected_total=12, completed_bytes=10), 10)
