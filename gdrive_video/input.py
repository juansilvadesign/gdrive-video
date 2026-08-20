"""Strict, pure parsing for accepted Google Drive source forms."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlsplit

from .errors import invalid_input

DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{25,100}$")
DRIVE_HOST = "drive.google.com"


def validate_drive_id(value: str) -> str:
    """Return a valid Drive ID or raise a stable invalid-input error."""

    if not DRIVE_ID_RE.fullmatch(value):
        raise invalid_input(
            "Invalid Google Drive file ID. Use a bare ID or a supported Drive file URL."
        )
    return value


def parse_drive_id(source: str) -> str:
    """Parse only documented Drive ID/URL forms; never mine arbitrary text."""

    candidate = source.strip()
    if not candidate or len(candidate) > 4096:
        raise invalid_input("The Google Drive source is empty or too long.")

    if DRIVE_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != DRIVE_HOST:
        raise invalid_input(
            "Unsupported source. Use an HTTPS drive.google.com file URL or a bare file ID."
        )
    try:
        port = parsed.port
    except ValueError:
        raise invalid_input("Drive URLs cannot contain an invalid port.") from None
    if parsed.username is not None or parsed.password is not None or port not in (None, 443):
        raise invalid_input("Drive URLs cannot contain credentials or a custom port.")
    if parsed.fragment:
        raise invalid_input("Drive URLs with fragments are not accepted.")

    path_segments = [unquote(part) for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20)

    file_id: str | None = None
    if len(path_segments) >= 3 and path_segments[0] == "file" and path_segments[1] == "d":
        if len(path_segments) > 4 or (len(path_segments) == 4 and path_segments[3] != "view"):
            raise invalid_input("Unsupported Google Drive file URL path.")
        file_id = path_segments[2]
        if "id" in query:
            raise invalid_input("Ambiguous Drive URL: both path and query IDs are present.")
    elif path_segments == ["open"]:
        ids = query.get("id", [])
        if len(ids) != 1:
            raise invalid_input("A Drive open URL must contain exactly one id parameter.")
        file_id = ids[0]
    else:
        raise invalid_input("Unsupported Google Drive URL form.")

    unexpected_ids = query.get("id", []) if path_segments != ["open"] else []
    if len(unexpected_ids) > 0:
        raise invalid_input("Ambiguous Drive URL.")
    return validate_drive_id(file_id)
