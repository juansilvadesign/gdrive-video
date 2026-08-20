"""Strict Netscape cookie loading with exact-host narrowing."""

from __future__ import annotations

import os
import re
import stat
import time
from dataclasses import dataclass
from http.cookiejar import Cookie
from pathlib import Path

import requests

from .errors import GDriveVideoError
from .models import FailureKind

MAX_COOKIE_FILE_BYTES = 1024 * 1024
COOKIE_HOST = "drive.google.com"
_COOKIE_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


@dataclass(frozen=True, slots=True)
class CookieLoadReport:
    loaded: int
    expired: int
    ignored: int


def _cookie_error(message: str) -> GDriveVideoError:
    return GDriveVideoError(FailureKind.AUTHENTICATION, message)


def _read_cookie_file(path_value: str | Path) -> str:
    path = Path(path_value).expanduser()
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        raise _cookie_error("The cookie file was not found.") from None
    except OSError:
        raise _cookie_error("The cookie file could not be inspected safely.") from None

    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise _cookie_error("The cookie source must be a regular, non-symlink file.")
    if metadata.st_size <= 0:
        raise _cookie_error("The cookie file is empty.")
    if metadata.st_size > MAX_COOKIE_FILE_BYTES:
        raise _cookie_error("The cookie file exceeds the 1 MiB safety limit.")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise _cookie_error("The cookie file must be owned by the current user.")
    if os.name != "nt" and metadata.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise _cookie_error(
            "Cookie file permissions are too broad; restrict it to the current user."
        )

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            current = os.fstat(handle.fileno())
            if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise _cookie_error("The cookie file changed while it was being opened.")
            raw = handle.read(MAX_COOKIE_FILE_BYTES + 1)
    except GDriveVideoError:
        raise
    except OSError:
        raise _cookie_error("The cookie file could not be read safely.") from None

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _cookie_error("The cookie file must be UTF-8 Netscape cookies.txt format.") from None


def _domain_applies_to_drive(domain: str) -> bool:
    normalized = domain.lower().lstrip(".").rstrip(".")
    return COOKIE_HOST == normalized or COOKIE_HOST.endswith(f".{normalized}")


def load_netscape_cookies(
    session: requests.Session,
    cookie_file: str | Path,
    *,
    now: float | None = None,
) -> CookieLoadReport:
    """Load unexpired eligible cookies and narrow them to drive.google.com."""

    text = _read_cookie_file(cookie_file)
    lines = text.splitlines()
    first_content = next((line.strip() for line in lines if line.strip()), "")
    if not first_content.lower().startswith("# netscape http cookie file"):
        raise _cookie_error(
            "Raw Cookie headers are not accepted. Export a Netscape cookies.txt file instead."
        )

    current_time = time.time() if now is None else now
    loaded = 0
    expired = 0
    ignored = 0
    for line_number, original_line in enumerate(lines, start=1):
        line = original_line.rstrip("\r\n")
        http_only = line.startswith("#HttpOnly_")
        if not line or (line.startswith("#") and not http_only):
            continue
        if http_only:
            line = line[len("#HttpOnly_") :]
        columns = line.split("\t")
        if len(columns) != 7:
            raise _cookie_error(
                f"The Netscape cookie file is malformed at data line {line_number}."
            )
        domain, include_subdomains, path, secure_text, expires_text, name, value = columns
        if include_subdomains not in {"TRUE", "FALSE"} or secure_text not in {
            "TRUE",
            "FALSE",
        }:
            raise _cookie_error(
                f"The Netscape cookie file is malformed at data line {line_number}."
            )
        if not _domain_applies_to_drive(domain):
            ignored += 1
            continue
        if (
            not path.startswith("/")
            or not name
            or not _COOKIE_NAME_RE.fullmatch(name)
            or any(ord(char) < 32 or ord(char) == 127 for char in domain + path + value)
        ):
            raise _cookie_error(
                f"The Netscape cookie file is malformed at data line {line_number}."
            )
        try:
            expires = int(expires_text)
        except ValueError:
            raise _cookie_error(
                f"The Netscape cookie file has an invalid expiry at data line {line_number}."
            ) from None
        if expires < 0:
            raise _cookie_error(
                f"The Netscape cookie file has an invalid expiry at data line {line_number}."
            )
        if expires > 0 and expires <= current_time:
            expired += 1
            continue
        if not value:
            ignored += 1
            continue

        narrowed = Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain=COOKIE_HOST,
            domain_specified=True,
            domain_initial_dot=False,
            path=path,
            path_specified=True,
            secure=True,
            expires=expires or None,
            discard=expires == 0,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": "true"} if http_only else {},
            rfc2109=False,
        )
        session.cookies.set_cookie(narrowed)
        loaded += 1

    if loaded == 0:
        if expired > 0:
            raise _cookie_error("All eligible cookies are expired; export a fresh Netscape jar.")
        raise _cookie_error("No eligible Google Drive cookies were found in the Netscape jar.")
    return CookieLoadReport(loaded=loaded, expired=expired, ignored=ignored)


def create_sessions(
    cookie_file: str | Path | None = None,
) -> tuple[requests.Session, requests.Session, CookieLoadReport | None]:
    """Return isolated metadata and cookie-free media sessions."""

    user_agent = "GDrive-Video/2.0 (+authorized-transfer)"
    metadata = requests.Session()
    media = requests.Session()
    metadata.headers.update({"User-Agent": user_agent})
    media.headers.update({"User-Agent": user_agent, "Accept-Encoding": "identity"})
    try:
        report = load_netscape_cookies(metadata, cookie_file) if cookie_file else None
    except Exception:
        metadata.close()
        media.close()
        raise
    return metadata, media, report
