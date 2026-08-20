# Authorized transfer contract

GDrive Video transfers one Google Drive video that the user already has permission
to view and save. It does not grant access, defeat authentication, determine legal
rights, or promise that every viewable file is downloadable.

## Input and authorization

Accepted inputs are a bare 25–100 character Drive file ID, an HTTPS
`drive.google.com/file/d/<id>` URL, or an HTTPS `drive.google.com/open?id=<id>` URL.
Other hosts, URL forms, fragments that contain another candidate, multiple `id`
values, and arbitrary surrounding text are rejected.

Private access accepts only a Netscape-format cookie export. Raw `Cookie:` headers
are rejected because they discard domain, path, Secure, and expiry boundaries.
Eligible unexpired Google cookies are narrowed to the exact metadata host. Media
requests use a separate cookie-free session. Cookie files must be owned by the
current user, private on POSIX, regular, non-symlink files, and at most 1 MiB.

Every request and redirect is validated before it is sent. Production traffic is
HTTPS-only. Metadata stays on the exact Drive host; media stays on the documented
Google media-host allowlist. Userinfo, credential-bearing URLs, downgrades,
unexpected ports/hosts, missing redirect locations, and more than five redirects
are terminal security errors.

## Output lifecycle

The final path is never used for in-progress bytes. A transfer writes to
`<final>.part` and stores non-secret state in `<final>.part.json`. The sidecar has a
schema version, Drive file ID, expected byte count when known, ETag/Last-Modified
when supplied, accepted content type, expected optional SHA-256, and completed
byte count. It never stores a playback URL, title, cookie, header, or response
body.

An existing final file is a conflict unless `--overwrite` was explicitly given.
Final, partial, and sidecar symlinks are always rejected. A partial without a
valid matching sidecar (or vice versa) is stale and preserved. `--restart`
archives stale/old partial artifacts under conflict-free `.stale.N` names before
starting; it never silently truncates them.

On resume, the request sends `Range` and a strong ETag or Last-Modified `If-Range`
when available. Append begins only after a `206` whose `Content-Range` starts at
the actual local byte count and whose total and validators agree with the sidecar.
A `200` response to a range request is never appended. A `416` completes only when
`bytes */total`, the local size, stored total, and stored validators agree.

Unknown-length responses stream until clean EOF with indeterminate progress. An
unknown-length partial without a validator is preserved but cannot be resumed
safely; the user must choose `--restart`.

## Completion and failure

Completion requires an accepted media status and type, identity content encoding,
a non-empty body, no HTML/JSON error signature, the expected range, the expected
byte count when known, an optional caller-provided SHA-256 match, a flushed and
`fsync`ed partial, and atomic promotion. Without `--overwrite`, promotion uses an
atomic no-replace operation; with it, replacement is explicit.

Connect and read timeouts are separate. Transient network errors, 429, and selected
5xx responses receive at most three attempts with bounded exponential backoff;
valid `Retry-After` values are honored within that bound. A failed active transfer
persists its latest recoverable state. Signed media authorization failure triggers
bounded metadata rediscovery, but resumption still requires the same media
identity.

Stable CLI exits are: `0` success, `2` invalid input, `3` authentication/cookie,
`4` authorization, `5` still processing, `6` non-video, `7` expired playback URL,
`8` throttled, `9` network, `10` disk/filesystem, `11` conflict/stale state, `12`
integrity/security, `70` internal error, and `130` cancellation.
