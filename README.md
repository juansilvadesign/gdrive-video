# GDrive Video

GDrive Video is a local Python CLI for transferring one Google Drive video that
you already have permission to access and save. It provides credential-scoped
metadata discovery, verified resume, content/size checks, and atomic final files.

It does not grant access, defeat Google authentication or product controls,
determine whether you have a legal right to save a file, or guarantee that every
viewable item has a downloadable media rendition. You are responsible for using
it only with files you own or are authorized to download.

## What the Milestone D CLI enforces

- Strict Drive ID/URL parsing; arbitrary surrounding text and unknown hosts fail.
- A separate cookie-bearing metadata session and cookie-free media session.
- HTTPS and host validation before every production request and redirect.
- Netscape cookie exports only, with expiry, owner, permissions, size, symlink,
  domain, path, and Secure checks.
- Signed URLs, cookies, cookie paths, headers, account hints, response snippets,
  and discovered private titles stay out of status output and resume sidecars.
- In-progress bytes live only in `<final>.part`; non-secret identity and byte state
  live in `<final>.part.json`.
- Resume appends only after a matching `206` and `Content-Range`. Ignored Range,
  changed validators/totals, and invalid `416` responses never append or promote.
- Unknown-length responses stream to clean EOF with indeterminate progress.
- Completion checks status, content type/encoding, error-body signatures, byte
  count when known, optional SHA-256, flush/`fsync`, and atomic promotion.
- Separate connect/read timeouts and at most three attempts by default, with
  bounded exponential backoff and `Retry-After` support.

The exact contract and stable exit codes are in
[`docs/transfer-contract.md`](docs/transfer-contract.md).

## Requirements and setup

Supported source/CI target: Python **3.10–3.13** on Windows, macOS, and Linux.
Use the project-local environment name `.venv` everywhere.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
run.bat --help
```

### macOS/Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --help
```

Launch scripts do not create environments or reinstall packages during ordinary
runs. Streamlit dependencies are separate in `requirements-streamlit.txt` and
development dependencies are in `requirements-dev.txt`.

## Usage

Accepted sources are:

- a bare 25–100 character Drive file ID;
- `https://drive.google.com/file/d/<id>` with optional `/view`;
- `https://drive.google.com/open?id=<id>` with exactly one `id`.

Examples:

```bash
# Default title-derived output in the current directory
.venv/bin/python main.py AAAAAAAAAAAAAAAAAAAAAAAAA

# Explicit output and optional known digest
.venv/bin/python main.py \
  "https://drive.google.com/file/d/AAAAAAAAAAAAAAAAAAAAAAAAA/view" \
  --output ./authorized-video.mp4 \
  --sha256 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# Archive an old partial instead of resuming it
.venv/bin/python main.py AAAAAAAAAAAAAAAAAAAAAAAAA \
  --output ./authorized-video.mp4 --restart
```

Run `python main.py --help` for chunk, timeout, retry, overwrite, cookie, account,
and verbose options. Chunk size must be 1 KiB–8 MiB. `--overwrite` is explicit and
only replaces a regular final file after the new partial has passed completion
checks. Symlinks are always refused.

### Private files and exported cookies

Use a disposable/test account where possible. Export only the Google cookies from
the browser profile that can already open the file, in **Netscape cookies.txt**
format. Raw `Cookie:` headers are rejected because they lose domain, path, Secure,
and expiry boundaries.

On macOS/Linux, make the export private before use:

```bash
chmod 600 ./cookies.txt
.venv/bin/python main.py AAAAAAAAAAAAAAAAAAAAAAAAA \
  --cookies-file ./cookies.txt
```

On Windows:

```powershell
run.bat AAAAAAAAAAAAAAAAAAAAAAAAA --cookies-file .\cookies.txt
```

Cookie files act like temporary login credentials. Do not commit, upload, email,
or paste them into issues. Delete the export manually when the transfer is done or
the session expires. The tool never deletes a user cookie file automatically.

Only eligible, unexpired Google cookies are cloned onto the exact
`drive.google.com` metadata host. The playback transfer uses a new cookie-free
session. A wrong account, expired jar, or insufficient permission remains an
authentication/authorization failure; the tool cannot expand your access.

## Resume, conflicts, and recovery

The final filename does not appear until completion. If a run stops, repeat the
same source and output options. The tool compares the actual `.part` size with its
sidecar, sends `Range` plus `If-Range` when possible, and appends only after the
server proves the expected start and identity.

If the server ignores Range, a validator/total changes, the sidecar is stale, or
an unknown-length partial has no validator, the old bytes are preserved and the
run fails truthfully. Inspect them or pass `--restart` to move both artifacts to
conflict-free `.stale.N` names before a fresh attempt. Nothing silently truncates
an old partial.

An existing final path exits as a conflict. Use another path or explicitly pass
`--overwrite`; replacement happens only after the new transfer is complete.

## Stable outcomes

| Exit | Outcome |
| ---: | --- |
| 0 | Success |
| 2 | Invalid input/configuration |
| 3 | Authentication or cookie problem |
| 4 | Authorization/unavailable file |
| 5 | Video still processing |
| 6 | Non-video or no media rendition |
| 7 | Signed playback authorization expired/refused |
| 8 | Throttled after bounded retries |
| 9 | Network/timeout/retry exhaustion |
| 10 | Disk/filesystem/promotion failure |
| 11 | Existing output or stale/conflicting state |
| 12 | Integrity, response, redirect, or identity failure |
| 70 | Unexpected internal error |
| 130 | User cancellation |

## Legacy Streamlit and extension surfaces

`streamlit.py` and `extension/` are legacy Milestones B/C surfaces. They do **not**
inherit Milestone D's redirect, credential, partial-file, resume, or integrity
contract. The Streamlit tester buffers a response in server memory; never give a
hosted instance browser cookies or use it for private, large, or sensitive files.
The Chromium extension retains broad debugger/host behavior pending Milestone E.

Use the CLI for the D safety guarantees. Streamlit/extension hardening is
deliberately deferred to Milestones E/F rather than represented as already safe.

## Development and verification

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest --cov --cov-report=term-missing
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python scripts/secret_scan.py --history
.venv/bin/pip-audit -r requirements.txt
```

The test suite is offline. A loopback fault server provides fresh/malformed
responses, resume negotiation, redirects, disconnects, retry statuses, and content
failures using generated bytes and visibly nonfunctional synthetic credentials.
Live Drive validation is an explicit manual release gate and must use
maintainer-owned fixtures.

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`TASKS.md`](TASKS.md),
[`ROADMAP.md`](ROADMAP.md), and [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT — see [`LICENSE`](LICENSE).
