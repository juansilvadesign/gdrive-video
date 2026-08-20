from __future__ import annotations

import os
import stat
import traceback
from pathlib import Path

import pytest
import requests

from gdrive_video.cookies import create_sessions, load_netscape_cookies
from gdrive_video.errors import GDriveVideoError


def write_cookie_file(path: Path, lines: list[str], mode: int = 0o600) -> None:
    path.write_text("# Netscape HTTP Cookie File\n" + "\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(mode)


def cookie_header(session: requests.Session, url: str) -> str | None:
    request = requests.Request("GET", url)
    return session.prepare_request(request).headers.get("Cookie")


def test_netscape_cookies_are_expiry_filtered_and_narrowed_to_exact_drive_host(
    tmp_path: Path,
) -> None:
    cookie_path = tmp_path / "cookies.txt"
    write_cookie_file(
        cookie_path,
        [
            ".google.com\tTRUE\t/\tTRUE\t4102444800\tSID\tUNUSABLE_SYNTHETIC_VALUE",
            ".google.com\tTRUE\t/\tTRUE\t1\tEXPIRED\tUNUSABLE_EXPIRED",
            ".example.invalid\tTRUE\t/\tTRUE\t4102444800\tOTHER\tUNUSABLE_OTHER",
        ],
    )
    metadata, media, report = create_sessions(cookie_path)
    try:
        assert report is not None
        assert (report.loaded, report.expired, report.ignored) == (1, 1, 1)
        assert cookie_header(metadata, "https://drive.google.com/u/0/get_video_info") == (
            "SID=UNUSABLE_SYNTHETIC_VALUE"
        )
        assert cookie_header(metadata, "https://docs.google.com/") is None
        assert cookie_header(metadata, "https://rr.googlevideo.com/video") is None
        assert cookie_header(media, "https://drive.google.com/u/0/get_video_info") is None
    finally:
        metadata.close()
        media.close()


def test_cookie_path_and_secure_attributes_are_preserved_and_narrowed(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies.txt"
    write_cookie_file(
        cookie_path,
        ["#HttpOnly_.google.com\tTRUE\t/u/0/\tFALSE\t4102444800\tSID\tUNUSABLE_VALUE"],
    )
    session = requests.Session()
    report = load_netscape_cookies(session, cookie_path)
    assert report.loaded == 1
    cookie = next(iter(session.cookies))
    assert cookie.domain == "drive.google.com"
    assert cookie.path == "/u/0/"
    assert cookie.secure is True
    assert cookie_header(session, "https://drive.google.com/u/0/get_video_info") is not None
    assert cookie_header(session, "https://drive.google.com/u/1/get_video_info") is None
    assert cookie_header(session, "http://drive.google.com/u/0/get_video_info") is None


@pytest.mark.parametrize(
    "contents",
    [
        "Cookie: SID=UNUSABLE\n",
        "SID=UNUSABLE; HSID=UNUSABLE\n",
        "# Netscape HTTP Cookie File\nmalformed\n",
        "# Netscape HTTP Cookie File\n.google.com\tTRUE\t/\tTRUE\tnot-time\tSID\tVALUE\n",
        "# Netscape HTTP Cookie File\n.google.com\tMAYBE\t/\tTRUE\t0\tSID\tVALUE\n",
        "# Netscape HTTP Cookie File\n.google.com\tTRUE\t/\tMAYBE\t0\tSID\tVALUE\n",
        "# Netscape HTTP Cookie File\n.google.com\tTRUE\t/\tTRUE\t-1\tSID\tVALUE\n",
        "# Netscape HTTP Cookie File\n.google.com\tTRUE\t/\x00\tTRUE\t0\tSID\tVALUE\n",
    ],
)
def test_raw_or_malformed_cookie_files_are_rejected_without_values(
    tmp_path: Path, contents: str
) -> None:
    cookie_path = tmp_path / "private-cookie-path.txt"
    cookie_path.write_text(contents, encoding="utf-8")
    cookie_path.chmod(0o600)
    session = requests.Session()
    with pytest.raises(GDriveVideoError) as caught:
        load_netscape_cookies(session, cookie_path)
    rendered = str(caught.value)
    assert "UNUSABLE" not in rendered
    assert str(cookie_path) not in rendered


def test_expired_only_cookie_jar_has_specific_safe_error(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies.txt"
    write_cookie_file(
        cookie_path,
        [".google.com\tTRUE\t/\tTRUE\t1\tSID\tUNUSABLE_EXPIRED"],
    )
    with pytest.raises(GDriveVideoError, match="expired"):
        load_netscape_cookies(requests.Session(), cookie_path)


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership/mode semantics")
def test_cookie_file_permissions_must_be_private(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies.txt"
    write_cookie_file(
        cookie_path,
        [".google.com\tTRUE\t/\tTRUE\t4102444800\tSID\tUNUSABLE"],
        mode=0o644,
    )
    with pytest.raises(GDriveVideoError, match="permissions"):
        load_netscape_cookies(requests.Session(), cookie_path)


def test_cookie_symlink_and_non_regular_sources_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    write_cookie_file(
        target,
        [".google.com\tTRUE\t/\tTRUE\t4102444800\tSID\tUNUSABLE"],
    )
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    with pytest.raises(GDriveVideoError, match="non-symlink"):
        load_netscape_cookies(requests.Session(), link)
    with pytest.raises(GDriveVideoError, match="regular"):
        load_netscape_cookies(requests.Session(), tmp_path)


def test_oversized_cookie_source_is_rejected_before_read(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies.txt"
    cookie_path.write_bytes(b"# Netscape HTTP Cookie File\n" + b"x" * (1024 * 1024))
    cookie_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    with pytest.raises(GDriveVideoError, match="1 MiB"):
        load_netscape_cookies(requests.Session(), cookie_path)


def test_missing_empty_and_unrelated_only_cookie_sources_are_distinct(tmp_path: Path) -> None:
    missing = tmp_path / "UNUSABLE_PRIVATE_COOKIE_PATH.txt"
    with pytest.raises(GDriveVideoError, match="not found") as caught:
        load_netscape_cookies(requests.Session(), missing)
    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert str(missing) not in rendered
    assert "FileNotFoundError" not in rendered

    empty = tmp_path / "empty.txt"
    empty.touch(mode=0o600)
    with pytest.raises(GDriveVideoError, match="empty"):
        load_netscape_cookies(requests.Session(), empty)

    unrelated = tmp_path / "unrelated.txt"
    write_cookie_file(
        unrelated,
        [".example.invalid\tTRUE\t/\tTRUE\t4102444800\tOTHER\tUNUSABLE_OTHER"],
    )
    with pytest.raises(GDriveVideoError, match="No eligible"):
        load_netscape_cookies(requests.Session(), unrelated)
