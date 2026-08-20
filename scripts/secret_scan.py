#!/usr/bin/env python3
"""Value-free repository/history credential-pattern check used by CI."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = (
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    re.compile(rb"gh[pousr]_[0-9A-Za-z]{36,255}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        rb"(?:^|[^A-Za-z])(?:SID|HSID|SSID|SAPISID|APISID)="
        rb"(?!UNUSABLE(?:_|\b)|<redacted>)([^.;\s]{8,})"
    ),
    re.compile(
        rb"videoplayback[^\s<>\"']{0,4096}(?:sig|lsig|spc)="
        rb"(?!UNUSABLE(?:_|\b))"
    ),
)
SKIP_SUFFIXES = {".png", ".ico", ".webp", ".pyc"}
SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SELF_PATH = "scripts/secret_scan.py"


def has_secret(data: bytes) -> bool:
    return any(pattern.search(data) for pattern in PATTERNS)


def scan_worktree(root: Path) -> list[str]:
    matches: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or relative.as_posix() == SELF_PATH
            or path.suffix.lower() in SKIP_SUFFIXES
            or SKIP_PARTS.intersection(relative.parts)
        ):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if has_secret(data):
            matches.append(relative.as_posix())
    return matches


def scan_history(root: Path) -> list[str]:
    result = subprocess.run(  # noqa: S603 -- fixed git command, no shell
        ["git", "rev-list", "--objects", "--all"],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    matches: set[str] = set()
    for line in result.stdout.splitlines():
        object_id, separator, path = line.partition(" ")
        if not separator or path == SELF_PATH or Path(path).suffix.lower() in SKIP_SUFFIXES:
            continue
        blob = subprocess.run(  # noqa: S603 -- validated object ID, no shell
            ["git", "cat-file", "-p", object_id],  # noqa: S607
            cwd=root,
            check=False,
            capture_output=True,
        )
        if blob.returncode == 0 and len(blob.stdout) <= 5 * 1024 * 1024 and has_secret(blob.stdout):
            matches.add(path)
    return sorted(matches)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    matches = scan_worktree(root)
    if args.history:
        matches.extend(scan_history(root))
    unique = sorted(set(matches))
    if unique:
        print("Credential-like patterns found in these paths (values suppressed):", file=sys.stderr)
        for path in unique:
            print(f"- {path}", file=sys.stderr)
        return 1
    print("Secret scan passed; no credential-like values found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
