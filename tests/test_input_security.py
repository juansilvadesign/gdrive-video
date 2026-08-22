from __future__ import annotations

import pytest
import requests
from conftest import SOURCE_ID

from gdrive_video.errors import GDriveVideoError
from gdrive_video.http import SecureHttpClient
from gdrive_video.input import parse_drive_id
from gdrive_video.models import MediaMetadata, Timeouts
from gdrive_video.security import UrlPolicy, UrlScope, redact_text, sanitize_url


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SOURCE_ID, SOURCE_ID),
        (f"https://drive.google.com/file/d/{SOURCE_ID}", SOURCE_ID),
        (f"https://drive.google.com/file/d/{SOURCE_ID}/view?usp=sharing", SOURCE_ID),
        (f"https://drive.google.com/open?id={SOURCE_ID}", SOURCE_ID),
    ],
)
def test_parse_drive_id_accepts_only_documented_forms(source: str, expected: str) -> None:
    assert parse_drive_id(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "prefix " + SOURCE_ID + " suffix",
        f"http://drive.google.com/file/d/{SOURCE_ID}",
        f"https://evil.example/file/d/{SOURCE_ID}",
        f"https://drive.google.com.evil.example/file/d/{SOURCE_ID}",
        f"https://user:password@drive.google.com/file/d/{SOURCE_ID}",
        f"https://drive.google.com:444/file/d/{SOURCE_ID}",
        "https://drive.google.com:invalid/file/d/" + SOURCE_ID,
        f"https://drive.google.com/file/d/{SOURCE_ID}/edit",
        f"https://drive.google.com/file/d/{SOURCE_ID}/view#another-{SOURCE_ID}",
        f"https://drive.google.com/open?id={SOURCE_ID}&id={'B' * 25}",
        f"https://drive.google.com/file/d/{SOURCE_ID}/view?id={'B' * 25}",
        "",
    ],
)
def test_parse_drive_id_rejects_ambiguous_or_untrusted_input(source: str) -> None:
    with pytest.raises(GDriveVideoError) as caught:
        parse_drive_id(source)
    assert caught.value.kind.value == "invalid_input"


@pytest.mark.parametrize(
    ("url", "scope"),
    [
        ("https://drive.google.com/get_video_info", UrlScope.METADATA),
        (
            "https://drive.google.com/videoplayback?sig=UNUSABLE_SYNTHETIC",
            UrlScope.MEDIA,
        ),
        ("https://drive.usercontent.google.com/video", UrlScope.MEDIA),
        ("https://rr1---sn.example.googlevideo.com/videoplayback", UrlScope.MEDIA),
        ("https://cdn.googleusercontent.com/video", UrlScope.MEDIA),
    ],
)
def test_url_policy_accepts_documented_https_hosts(url: str, scope: UrlScope) -> None:
    assert UrlPolicy().validate(url, scope) == url


@pytest.mark.parametrize(
    ("url", "scope"),
    [
        ("http://drive.google.com/get_video_info", UrlScope.METADATA),
        ("https://drive.google.com.evil.invalid/video", UrlScope.MEDIA),
        ("https://googlevideo.com.evil.invalid/video", UrlScope.MEDIA),
        ("https://user:pass@drive.google.com/video", UrlScope.MEDIA),
        ("https://drive.google.com:8443/video", UrlScope.MEDIA),
        ("https://example.com/video", UrlScope.MEDIA),
        ("https://rr.googlevideo.com/video", UrlScope.METADATA),
    ],
)
def test_url_policy_rejects_downgrades_credentials_and_unknown_hosts(
    url: str, scope: UrlScope
) -> None:
    with pytest.raises(GDriveVideoError):
        UrlPolicy().validate(url, scope)


def test_redirects_are_validated_and_sensitive_headers_stripped(fault_server) -> None:
    policy = UrlPolicy(test_origins=frozenset({fault_server.origin}))
    client = SecureHttpClient(policy)
    session = requests.Session()
    response = client.request(
        session,
        "GET",
        f"{fault_server.base_url}/redirect-known",
        scope=UrlScope.MEDIA,
        headers={"aUtHoRiZaTiOn": "Bearer UNUSABLE", "cOoKiE": "SID=UNUSABLE"},
        timeouts=Timeouts(2, 2),
    )
    response.close()
    assert len(fault_server.state.requests) == 2
    assert fault_server.state.requests[0]["authorization"] is None
    assert fault_server.state.requests[0]["cookie"] is None
    assert fault_server.state.requests[1]["authorization"] is None
    assert fault_server.state.requests[1]["cookie"] is None
    session.close()


def test_unknown_redirect_is_refused_before_request(fault_server) -> None:
    policy = UrlPolicy(test_origins=frozenset({fault_server.origin}))
    client = SecureHttpClient(policy)
    session = requests.Session()
    with pytest.raises(GDriveVideoError):
        client.request(
            session,
            "GET",
            f"{fault_server.base_url}/redirect-unknown",
            scope=UrlScope.MEDIA,
            timeouts=Timeouts(2, 2),
        )
    assert [item["path"] for item in fault_server.state.requests] == ["/redirect-unknown"]
    session.close()


def test_redaction_removes_queries_headers_account_hints_and_registered_secrets() -> None:
    secret_path = "/private/account/cookies.txt"
    raw = (
        "GET https://rr.googlevideo.com/videoplayback?expire=1&sig=UNUSABLE_SYNTHETIC\n"
        "Cookie: SID=UNUSABLE_SYNTHETIC; __Secure-1PSID=UNUSABLE_SYNTHETIC\n"
        "Authorization: Bearer UNUSABLE_SYNTHETIC\n"
        "https://drive.google.com/u/7/get_video_info " + secret_path
    )
    redacted = redact_text(raw, (secret_path,))
    assert "UNUSABLE_SYNTHETIC" not in redacted
    assert "expire=1" not in redacted
    assert "sig=" not in redacted
    assert secret_path not in redacted
    assert "/u/7/" not in redacted
    assert "<redacted>" in redacted


def test_redaction_covers_bare_cookie_pairs_outside_a_header() -> None:
    """A cookie pair with no `Cookie:` prefix is not reachable by the header rule."""
    redacted = redact_text("replaying SID=UNUSABLE_SYNTHETIC after a stalled read")
    assert "UNUSABLE_SYNTHETIC" not in redacted
    assert "SID=<redacted>" in redacted


def test_sanitize_url_never_keeps_query_or_fragment() -> None:
    safe = sanitize_url("https://drive.google.com/u/2/path?token=SECRET#fragment")
    assert safe == "https://drive.google.com/u/<redacted>/path?<redacted>"


def test_media_metadata_repr_hides_playback_url() -> None:
    metadata = MediaMetadata(SOURCE_ID, "https://example.invalid/?secret=VALUE", "title")
    rendered = repr(metadata)
    assert "secret" not in rendered
    assert "VALUE" not in rendered
