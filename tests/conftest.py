from __future__ import annotations

import socket
import threading
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlsplit

import pytest

SOURCE_ID = "A" * 25
MEDIA_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + bytes(range(256)) * 512
ETAG = '"synthetic-etag-v1"'
LAST_MODIFIED = "Wed, 20 Aug 2025 12:00:00 GMT"


@dataclass
class ServerState:
    requests: list[dict[str, str | None]] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)
    stall_release: threading.Event = field(default_factory=threading.Event)


class FaultHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: FaultServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        self.server.state.counts[parsed.path] += 1
        self.server.state.requests.append(
            {
                "path": parsed.path,
                "range": self.headers.get("Range"),
                "if_range": self.headers.get("If-Range"),
                "cookie": self.headers.get("Cookie"),
                "authorization": self.headers.get("Authorization"),
            }
        )
        if parsed.path == "/metadata":
            self._metadata(parse_qs(parsed.query))
            return
        self._media(parsed.path)

    def _metadata(self, query: dict[str, list[str]]) -> None:
        metadata_status = (query.get("meta_status") or ["200"])[0]
        if metadata_status != "200":
            self.send_response(int(metadata_status))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        mode = (query.get("meta_mode") or ["ok"])[0]
        if mode == "html":
            body = b"<!doctype html><html>synthetic login</html>"
            self._send(body, content_type="text/html")
            return
        media_path = (query.get("media") or ["/fresh"])[0]
        playback = f"{self.server.base_url}{media_path}?test_token=UNUSABLE_SYNTHETIC_TOKEN"
        if mode == "processing":
            body = urlencode({"status": "fail", "reason": "still processing"}).encode()
        elif mode == "nonvideo":
            body = urlencode({"status": "ok", "title": "synthetic"}).encode()
        elif mode == "conflicting-title":
            body = urlencode(
                [
                    ("status", "ok"),
                    ("title", "one.mp4"),
                    ("title", "two.mp4"),
                    ("fmt_stream_map", f"18|{playback}"),
                ]
            ).encode()
        elif mode == "missing-title":
            body = urlencode({"status": "ok", "fmt_stream_map": f"18|{playback}"}).encode()
        else:
            body = urlencode(
                {
                    "status": "ok",
                    "title": "synthetic-fixture.mp4",
                    "fmt_stream_map": f"18|{playback}",
                }
            ).encode()
        self._send(body, content_type="application/x-www-form-urlencoded")

    def _media(self, path: str) -> None:
        range_header = self.headers.get("Range")
        if path == "/ignore-range":
            self._send_video(MEDIA_BYTES)
            return
        if path == "/unknown":
            self._send_video(MEDIA_BYTES, include_length=False)
            return
        if path == "/html":
            self._send(b"<!doctype html><html>synthetic error</html>", content_type="text/html")
            return
        if path == "/json":
            self._send(b'{"error":"synthetic"}', content_type="application/json")
            return
        if path == "/empty":
            self._send_video(b"")
            return
        if path == "/encoded":
            self._send_video(MEDIA_BYTES, extra={"Content-Encoding": "gzip"})
            return
        if path == "/redirect-known":
            self._redirect(f"{self.server.base_url}/fresh?test_token=UNUSABLE_REDIRECT")
            return
        if path == "/redirect-unknown":
            self._redirect("https://untrusted.invalid/video?test_token=UNUSABLE_REDIRECT")
            return
        if path == "/redirect-http":
            self._redirect("http://drive.google.com/file")
            return
        if path == "/redirect-loop":
            self._redirect("/redirect-loop")
            return
        if path == "/status403":
            self._status(403)
            return
        if path == "/status404":
            self._status(404)
            return
        if path == "/retry429" and self.server.state.counts[path] < 3:
            self._status(429, {"Retry-After": "2"})
            return
        if path == "/retry500" and self.server.state.counts[path] < 3:
            self._status(503)
            return
        if path == "/disconnect" and self.server.state.counts[path] == 1:
            amount = 4096
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(MEDIA_BYTES)))
            self.send_header("ETag", ETAG)
            self.send_header("Last-Modified", LAST_MODIFIED)
            self.end_headers()
            self.wfile.write(MEDIA_BYTES[:amount])
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if path == "/stall":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(MEDIA_BYTES)))
            self.send_header("ETag", ETAG)
            self.send_header("Last-Modified", LAST_MODIFIED)
            self.end_headers()
            self.wfile.flush()
            self.server.state.stall_release.wait()
            return
        if path == "/invalid416":
            self._status(
                416,
                {
                    "Content-Range": f"bytes */{len(MEDIA_BYTES) + 10}",
                    "ETag": ETAG,
                    "Last-Modified": LAST_MODIFIED,
                },
            )
            return
        if path == "/wrong-start" and range_header:
            start = int(range_header.removeprefix("bytes=").split("-", 1)[0])
            body = MEDIA_BYTES[start:]
            self._send_video(
                body,
                status=206,
                extra={
                    "Content-Range": f"bytes {start + 1}-{len(MEDIA_BYTES) - 1}/{len(MEDIA_BYTES)}"
                },
            )
            return
        if path == "/wrong-total" and range_header:
            start = int(range_header.removeprefix("bytes=").split("-", 1)[0])
            body = MEDIA_BYTES[start:]
            self._send_video(
                body,
                status=206,
                extra={
                    "Content-Range": f"bytes {start}-{len(MEDIA_BYTES) - 1}/{len(MEDIA_BYTES) + 1}"
                },
            )
            return
        if path == "/changed-etag" and range_header:
            self._range_response(range_header, etag='"synthetic-etag-v2"')
            return
        self._range_response(range_header)

    def _range_response(self, range_header: str | None, *, etag: str = ETAG) -> None:
        if not range_header:
            self._send_video(MEDIA_BYTES, etag=etag)
            return
        start = int(range_header.removeprefix("bytes=").split("-", 1)[0])
        if start >= len(MEDIA_BYTES):
            self._status(
                416,
                {
                    "Content-Range": f"bytes */{len(MEDIA_BYTES)}",
                    "ETag": etag,
                    "Last-Modified": LAST_MODIFIED,
                },
            )
            return
        body = MEDIA_BYTES[start:]
        self._send_video(
            body,
            status=206,
            etag=etag,
            extra={"Content-Range": f"bytes {start}-{len(MEDIA_BYTES) - 1}/{len(MEDIA_BYTES)}"},
        )

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", "MEDIA_TEST=UNUSABLE_SYNTHETIC; Path=/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _status(self, status: int, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_video(
        self,
        body: bytes,
        *,
        status: int = 200,
        include_length: bool = True,
        etag: str = ETAG,
        extra: dict[str, str] | None = None,
    ) -> None:
        headers = {"ETag": etag, "Last-Modified": LAST_MODIFIED, **(extra or {})}
        self._send(
            body,
            status=status,
            content_type="video/mp4",
            include_length=include_length,
            extra=headers,
        )

    def _send(
        self,
        body: bytes,
        *,
        status: int = 200,
        content_type: str,
        include_length: bool = True,
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if include_length:
            self.send_header("Content-Length", str(len(body)))
        else:
            self.send_header("Connection", "close")
            self.close_connection = True
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)


class FaultServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, _request, _client_address) -> None:
        """Disconnect/reset behavior is intentional in fault-injection routes."""

        return

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), FaultHandler)
        self.state = ServerState()
        host, port = self.server_address
        self.base_url = f"http://{host}:{port}"

    @property
    def origin(self) -> tuple[str, str, int]:
        host, port = self.server_address
        return ("http", str(host), int(port))

    def endpoint_template(
        self,
        media: str,
        *,
        meta_mode: str = "ok",
        meta_status: int = 200,
    ) -> str:
        return (
            f"{self.base_url}/metadata?media={quote(media, safe='')}"
            f"&meta_mode={quote(meta_mode)}&meta_status={meta_status}"
            "&docid={source_id}&account={account_index}"
        )


@pytest.fixture
def fault_server() -> Iterator[FaultServer]:
    server = FaultServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.state.stall_release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
