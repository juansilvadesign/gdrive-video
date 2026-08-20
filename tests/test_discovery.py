from __future__ import annotations

import json
from urllib.parse import urlencode

import pytest
from conftest import SOURCE_ID

from gdrive_video.discovery import MAX_METADATA_BYTES, parse_drive_metadata
from gdrive_video.errors import GDriveVideoError
from gdrive_video.security import UrlPolicy

POLICY = UrlPolicy()


def parse(body: bytes, *, credentials: bool = False):
    return parse_drive_metadata(
        body,
        source_id=SOURCE_ID,
        policy=POLICY,
        credentials_supplied=credentials,
    )


def test_structured_form_parser_preserves_encoded_title_and_url_delimiters() -> None:
    playback = (
        "https://rr1.googlevideo.com/videoplayback?label=A%2CB%3DC&test_token=UNUSABLE_SYNTHETIC"
    )
    body = urlencode(
        {
            "status": "ok",
            "title": "A & B = C.mp4",
            "fmt_stream_map": f"18|{playback}",
        }
    ).encode()
    metadata = parse(body)
    assert metadata.title == "A & B = C.mp4"
    assert metadata.playback_url == playback


def test_multiple_streams_choose_first_deterministically_without_quality_claim() -> None:
    first = "https://one.googlevideo.com/videoplayback?test_token=ONE"
    second = "https://two.googlevideo.com/videoplayback?test_token=TWO"
    body = urlencode({"fmt_stream_map": f"18|{first},22|{second}", "title": "x"}).encode()
    assert parse(body).playback_url == first


def test_descriptor_and_player_response_stream_formats_are_supported() -> None:
    descriptor_url = "https://one.googlevideo.com/videoplayback?test_token=DESCRIPTOR"
    descriptor = urlencode({"url": descriptor_url, "type": "video/webm; codecs=vp9"})
    body = urlencode({"url_encoded_fmt_stream_map": descriptor}).encode()
    metadata = parse(body)
    assert metadata.playback_url == descriptor_url
    assert metadata.content_type == "video/webm"

    player_url = "https://two.googlevideo.com/videoplayback?test_token=PLAYER"
    player = json.dumps(
        {"streamingData": {"formats": [{"url": player_url, "mimeType": "video/mp4; codecs=avc1"}]}}
    )
    metadata = parse(urlencode({"player_response": player}).encode())
    assert metadata.playback_url == player_url
    assert metadata.content_type == "video/mp4"


def test_direct_url_field_and_type_query_are_supported() -> None:
    playback = (
        "https://direct.googlevideo.com/videoplayback?type=video%2Fwebm&test_token=UNUSABLE_DIRECT"
    )
    metadata = parse(urlencode({"url": playback}).encode())
    assert metadata.playback_url == playback
    assert metadata.content_type == "video/webm"


@pytest.mark.parametrize(
    "player",
    [
        "not-json",
        json.dumps([]),
        json.dumps({"streamingData": []}),
        json.dumps({"streamingData": {"formats": "wrong"}}),
        json.dumps({"streamingData": {"formats": [None, {"url": 4}]}}),
    ],
)
def test_invalid_player_response_shapes_fail_as_non_video(player: str) -> None:
    with pytest.raises(GDriveVideoError) as caught:
        parse(urlencode({"player_response": player}).encode())
    assert caught.value.kind.value == "non_video"


def test_missing_title_is_allowed_for_safe_id_fallback() -> None:
    playback = "https://rr.googlevideo.com/videoplayback?test_token=MISSING_TITLE"
    metadata = parse(urlencode({"fmt_stream_map": f"18|{playback}"}).encode())
    assert metadata.title is None


def test_conflicting_titles_are_rejected() -> None:
    playback = "https://rr.googlevideo.com/videoplayback?test_token=CONFLICT"
    body = urlencode(
        [("title", "one"), ("title", "two"), ("fmt_stream_map", f"18|{playback}")]
    ).encode()
    with pytest.raises(GDriveVideoError, match="conflicting"):
        parse(body)


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (urlencode({"status": "fail", "reason": "still processing"}).encode(), "processing"),
        (urlencode({"status": "fail", "reason": "login required"}).encode(), "authentication"),
        (urlencode({"status": "fail", "reason": "access denied"}).encode(), "authorization"),
        (urlencode({"status": "ok", "title": "document"}).encode(), "non_video"),
    ],
)
def test_metadata_failure_states_are_distinct(body: bytes, kind: str) -> None:
    with pytest.raises(GDriveVideoError) as caught:
        parse(body)
    assert caught.value.kind.value == kind


def test_html_metadata_maps_to_auth_without_retaining_body() -> None:
    marker = "UNUSABLE_RESPONSE_MARKER"
    with pytest.raises(GDriveVideoError) as caught:
        parse(f"<!doctype html><html>{marker}</html>".encode(), credentials=True)
    assert caught.value.kind.value == "authentication"
    assert marker not in str(caught.value)


def test_oversized_and_empty_metadata_are_rejected() -> None:
    for body in (b"", b"x" * (MAX_METADATA_BYTES + 1)):
        with pytest.raises(GDriveVideoError) as caught:
            parse(body)
        assert caught.value.kind.value == "integrity"


def test_invalid_utf8_and_unknown_failure_reason_are_safe() -> None:
    with pytest.raises(GDriveVideoError) as malformed:
        parse(b"title=\xff")
    assert malformed.value.kind.value == "integrity"

    body = urlencode({"status": "fail", "reason": "synthetic unknown"}).encode()
    with pytest.raises(GDriveVideoError) as failed:
        parse(body)
    assert failed.value.kind.value == "authorization"


def test_unknown_stream_host_is_terminal_security_failure() -> None:
    body = urlencode({"fmt_stream_map": "18|https://evil.invalid/video?token=UNUSABLE"}).encode()
    with pytest.raises(GDriveVideoError, match="unexpected host"):
        parse(body)
