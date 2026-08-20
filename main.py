#!/usr/bin/env python3
"""GDrive Video command-line entry point."""

from __future__ import annotations

import sys

from gdrive_video.cli import run

if __name__ == "__main__":
    sys.exit(run())
