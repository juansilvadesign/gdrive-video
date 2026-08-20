# Changelog

All notable changes are documented here. The project remains at version 2.0 until
Milestone D's automated matrix and maintainer-owned manual release evidence are
both green.

## Unreleased — Milestone D

### Added

- Typed, UI-neutral discovery/transfer request, progress, result, failure, timeout,
  retry, media-identity, output-plan, and resume-state contracts.
- Strict accepted Drive ID/URL parser and centralized host/redirect validation.
- `.part` plus schema-versioned non-secret `.part.json` lifecycle, optional
  expected SHA-256, deterministic recovery states, `--restart`, and explicit
  `--overwrite`.
- Matching `206`/`Content-Range` resume negotiation, validator/total checks,
  validated `416`, unknown-length EOF completion, and atomic final promotion.
- Separate connect/read timeouts, bounded retries/backoff, `Retry-After`, signed-URL
  rediscovery, stable failure outcomes, and stable process exit codes.
- Offline generated-media HTTP fault matrix, filesystem/cookie/redaction tests,
  cross-platform CI, formatter/lint/type checks, history-aware secret scan,
  dependency audit, license report, and Dependabot configuration.

### Changed

- Netscape cookies are expiry-filtered and narrowed to the exact Drive metadata
  host. Media transfers use a separate cookie-free session.
- Raw Cookie-header files are rejected with migration guidance because they cannot
  preserve domain/path/Secure/expiry boundaries.
- Metadata-body timeouts/disconnects receive the same bounded, redacted retry
  treatment as connection failures.
- Output names handle control/invalid characters, Windows reserved names, trailing
  dots/spaces, missing titles, explicit directories, collisions, and symlinks.
- Files appear at the final path only after media/content/size/digest checks,
  flush/`fsync`, and atomic promotion.
- Status/verbose output no longer includes signed URLs, cookie paths, account hints,
  response snippets, discovered private titles, or destination-derived titles.
- `requirements.txt` is UTF-8 and contains CLI runtime dependencies only;
  Streamlit and development dependencies are separated.
- CI targets Python 3.10–3.13 on Windows, macOS, and Linux; release support remains
  provisional until that matrix is green. Launchers and docs consistently use
  `.venv` and never reinstall packages during an ordinary launch.
- Authorized-use language replaces claims about access-control circumvention.

### Security

- Removed the unused tracked `.streamlit/secrets.toml`; real Streamlit secret files
  are ignored.
- Cookie sources must be small, owned, private regular non-symlink files where the
  operating system exposes those checks; malformed flags, controls, and negative
  expiries are rejected.
- Production requests require HTTPS, reject userinfo/custom ports, and validate
  every metadata/media redirect against a narrow host policy.
- Media requests strip caller-supplied credential headers case-insensitively, and
  controlled domain errors suppress raw underlying exception chains.
- Signed playback URLs remain short-lived in memory and never enter sidecars or
  controlled exception messages.

### Compatibility and legacy surfaces

- Raw Cookie-header files no longer work; export Netscape cookies.txt instead.
- Existing files are conflicts unless `--overwrite` is explicit. Legacy direct-to-
  final partials are not auto-adopted because they have no trustworthy identity.
- `streamlit.py` and the Chromium extension remain legacy Milestones B/C surfaces
  and do not inherit the Milestone D CLI contract.
