# Contributing

Contributions are welcome when they preserve the authorized-use, credential, and
file-integrity boundaries in [`docs/transfer-contract.md`](docs/transfer-contract.md).
Milestone D is intentionally one safe single-file transfer; batch, rendition,
extension, and GUI work follow the sequencing in [`ROADMAP.md`](ROADMAP.md).

## Development environment

Use Python 3.10–3.13 and the single project environment name `.venv`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
```

On Windows, replace `.venv/bin/python` with
`.venv\Scripts\python.exe`. Launchers never install dependencies automatically.

## Before opening a pull request

Run:

```bash
.venv/bin/python -m pytest --cov --cov-report=term-missing
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python scripts/secret_scan.py --history
.venv/bin/pip-audit -r requirements.txt
.venv/bin/pip-licenses --format=plain-vertical
```

The GitHub Actions matrix repeats the offline suite on Windows, macOS, and Linux
with Python 3.10–3.13. Do not make CI depend on Google Drive or another public
network service.

## Fixture and fault-test rules

- Generate small deterministic bytes or use maintainer-authored media. Never add
  third-party copyrighted video.
- Metadata fixtures must be sanitized and bounded. Keep only the fields needed to
  exercise the parser.
- Cookie names/values and signed-query fields must be visibly nonfunctional, using
  the `UNUSABLE_SYNTHETIC` convention.
- Never commit live Drive IDs, playback URLs, private titles, cookie paths/values,
  authorization headers, response captures, or account identifiers.
- Extend the loopback fault server for HTTP behavior. A change to resume logic must
  test exact output bytes/hash plus its failure-side non-append/non-promotion
  behavior.
- Filesystem changes need tests for conflict, symlink, stale sidecar, cancellation,
  permission/write failure, and atomic-promotion failure where applicable.
- Retry tests inject a sleep callback; tests must never really wait.

The history-aware secret scanner reports paths only and suppresses values. If it
flags a real credential, stop work, notify its owner privately, revoke/rotate it,
remove it from artifacts/history as appropriate, and only then continue. Do not
paste it into an issue or pull request.

## Credential and logging rules

Treat cookies, authorization headers, response bodies, signed media URLs, private
titles, and account hints as sensitive. Domain errors use controlled messages; do
not interpolate a `requests` exception, response snippet, URL, cookie path, header,
or jar entry. Use centralized redaction as defense in depth.

Metadata cookies remain on the exact Drive metadata host. Media code must use the
separate cookie-free session. Every redirect is validated before sending the next
request. New Google host suffixes require owned-fixture traffic evidence and a
focused policy/test change; do not broaden to a convenience wildcard.

Raw `Cookie:` files remain rejected unless a future design can restore domain,
path, Secure, and expiry semantics without guessing. Never weaken cookie-file
owner, mode, symlink, type, or size checks to make a fixture easier to load.

## Transfer invariants

- Validate chunk/timeouts/retries/digest before network or filesystem mutation.
- Never write transfer bytes directly to the final path.
- Never append before a matching `206`, start offset, total, and stored validators.
- Never treat an unvalidated `416`, missing length, ignored Range, or changed media
  identity as completion.
- Keep signed URLs and titles out of sidecars.
- Flush, `fsync`, verify, then atomically promote. Preserve partials on failure.
- UI adapters render typed progress/results; deep helpers do not print.

If a change cannot preserve an invariant, propose a contract/roadmap change first
instead of silently changing behavior.

## Manual release evidence

Automated tests are necessary but cannot prove live Drive behavior. Before a
Milestone D release, a maintainer must use only owned fixtures to test public and
authorized private fresh/resumed transfers, expired/wrong-account cookies,
processing/non-video content, signed-URL expiry, conflict, cancellation, and
traffic/log redaction. Compare the final byte count and SHA-256 to the local source.

Record only sanitized pass/fail evidence, supported OS/Python matrix, and the
release commit/tag in `docs/milestone-d-evidence.md`. Do not record fixture IDs,
titles, URLs, cookie paths, or response bodies. D is not marked shipped until both
automated and manual evidence are green.

## Pull request scope

Keep commits focused, explain which contract and tests changed, and update README,
tasks, roadmap, and changelog when behavior or compatibility changes. Preserve
unrelated work in a dirty tree. Use respectful, specific review discussion and the
repository code of conduct.
