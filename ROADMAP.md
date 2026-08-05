# Roadmap

Where GDrive Video goes after its CLI, browser-extension, Streamlit, and cookie
support releases.

**Direction:** turn a collection of Google Drive video download surfaces into an
**authorized, credential-safe, integrity-aware transfer tool**: a user who already
has legitimate access can download an owned/permitted video, interrupt and resume
without corruption, and know exactly what completed—without exposing browser
cookies or signed media URLs.

This file owns strategy, release boundaries, and status. The actionable checklist
lives in **[`TASKS.md`](TASKS.md)**.

_Last reviewed: 2026-08-05_

---

## Fixed frame

No calendar deadline or monetary budget was supplied. The inferred planning
baseline below keeps the roadmap responsive instead of committing to every item in
the README wish list:

| Constraint | Fixed planning baseline |
| --- | --- |
| **Outcome** | An authorized user can identify a Google Drive video they can already view, transfer it without leaking session credentials, safely resume interruptions, and verify that the final file is complete and is the intended media. |
| **Deadline** | End of the eighth calendar week after implementation kickoff. Record the kickoff and resulting end date before Milestone D starts; do not extend the eight-week window. |
| **Capacity budget** | One maintainer, at most **40 maintainer-days** across Milestones D–G. No paid infrastructure. |
| **Scope** | Open. Milestone D is protected; later releases are re-cut, reordered, or deferred as evidence and capacity change. |

The following constraints stay fixed throughout the window:

- The tool is for videos the user owns or is authorized to download. It does not
  grant access, defeat authentication, or make a legal/policy determination for
  the user.
- Cookies, authorization headers, response bodies, and signed media URLs are
  credentials. They are minimized, memory-bounded, redacted, never committed, and
  never sent to an unverified host.
- A resumed download appends only after a verified `206` response and matching
  `Content-Range`. Unknown length, ignored ranges, changed validators, and `416`
  each have explicit behavior.
- Incomplete data stays in a `.part` artifact. A final filename appears only after
  completion checks and an atomic promotion.
- CLI, future local GUI, and extension may discover media differently, but shared
  ID parsing, metadata, filename, transfer, status, and redaction semantics do not
  drift.
- Private videos are not proxied through a public hosted service or buffered in a
  third party's memory. Any retained web experience is local-first and bounded.
- Quality selection, batch work, subtitles, and metadata enrichment wait until one
  transfer is correct, resumable, and safe.

If 40 days cannot buy every planned release, ship fewer complete benefits. Do not
trade credential containment or file integrity for later convenience features.

---

## Current baseline and why integrity comes next

The repository has three shipped increments: a Python CLI, a Chromium extension
plus Streamlit distribution surface, and exported-browser-cookie support added in
`5e85a2e`. The product can discover Drive playback URLs, download with progress,
attempt a Range resume, capture progressive transcodes in Chrome, and guide users
who need their signed-in profile. Its next constraint is the trust boundary around
those capabilities.

| Observed behavior | Consequence | Roadmap response |
| --- | --- | --- |
| When a partial file exists, the CLI opens it in append mode before proving the server honored `Range`; a `200` response is accepted alongside `206`. | A server that ignores Range can append the full video to the partial file and report success with corrupted output. | Milestone D verifies resume negotiation before writing. |
| Missing `Content-Length` can be interpreted as “already fully downloaded,” and any `416` is treated as complete. | A valid unknown-length stream can be skipped, while an oversized/corrupt local file can be blessed as complete. | Stream to EOF when length is unknown and validate `416` against remote total. |
| Files are written directly to their final names without source validators or a resume sidecar. | An interruption, changed signed URL, or replaced Drive file can mix bytes without a durable identity check. | Use `.part` plus source/ETag/Last-Modified/size metadata and atomic promotion. |
| Verbose mode prints the full signed playback URL and cookie-file path; raw cookie headers become domainless session cookies and expired Netscape cookies are loaded. | Session material can leak to logs or be sent more broadly than intended. | D scopes, expires, redacts, and tests every credential path. |
| Drive metadata is parsed with string splitting in both `main.py` and `streamlit.py`. | Encoded delimiters, response changes, and duplicate fixes can produce wrong title/media extraction. | Extract one structured, fixture-tested discovery core. |
| Streamlit downloads `video_response.content` before rendering its button. | A large private video is fully buffered in server memory and proxied through the host, with no resume or hard size boundary. | F becomes a bounded local GUI instead of a private-video public proxy. |
| The extension requests `debugger` plus `<all_urls>`, enables capture globally, stores complete response bodies, and sends captured signed URLs to the popup. | A narrowly intended Drive action has a broad browser and credential exposure surface. | E limits activation, hosts, retained data, lifetime, and messages. |
| The extension assumes the final progressive transcode is highest quality. | Ordering changes can select an unintended rendition with no user-visible evidence. | E parses explicit rendition metadata and lets evidence drive selection. |
| No unit/integration/extension tests or CI exist. | Resume, cookie, redirect, parser, and cleanup regressions have no automated barrier. | D builds a credential-safe local HTTP test matrix and release checks. |
| `requirements.txt` is UTF-16; Docker copies only `streamlit.py` while the app offers an extension ZIP; launchers use both `.env` and `.venv`; the devcontainer disables XSRF protection. | Clean installs and deployed behavior are inconsistent or broken across surfaces. | Normalize packaging/configuration and verify each claimed path before release. |
| A tracked `.streamlit/secrets.toml` contains repository/file configuration and current code does not read `st.secrets`. | A secrets path is used for non-runtime config and creates a dangerous precedent for future credentials. | Classify/remove it, ignore real secrets, audit history, and provide a safe example only if needed. |
| README/Streamlit copy markets “bypass,” “protected,” and “any video” behavior. | The product overstates capability and obscures the user's authorization responsibility. | Replace it with precise authorized-use and technical-limit language. |

---

## Milestones

`✅ shipped` · `▶ next` · `⬜ later`

| | Benefit-delivering release | State | Capacity ceiling | Assumption retired |
| --- | --- | --- | --- | --- |
| **A** | Interactive/resumable Python CLI | ✅ | Shipped | Users need a local way to transfer viewable Drive videos. |
| **B** | Chromium capture and Streamlit distribution | ✅ | Shipped | Browser and GUI entry points reduce discovery/setup friction. |
| **C** | Authenticated Chrome-profile cookie support | ✅ | Shipped | Some authorized private links require the user's existing signed-in session. |
| **D** | Credential-safe, integrity-aware single download | ▶ | 14 days | Correct resume and explicit outcomes create enough trust for real large files. |
| **E** | Least-privilege in-browser capture | ⬜ | 10 days | Users value browser convenience enough to accept a narrowly explained debugger permission. |
| **F** | Bounded local GUI for non-CLI users | ⬜ | 9 days | A local visual workflow improves accessibility without proxying private media through a host. |
| **G** | Rendition choice and small authorized queue | ⬜ | 7 days | Quality choice and a bounded queue solve frequent work only after single-transfer safety is proven. |

The current order is **A → B → C → D → E → F → G**. Only D is detailed enough
to execute. E–G are option boundaries, not promises; re-plan them after each
shipped release.

### A — Interactive/resumable Python CLI ✅

The original release accepts a Drive URL or ID, discovers a playback URL/title,
tracks progress, supports custom naming/chunk size, and attempts to continue an
existing file with an HTTP Range request. Windows launch support makes the local
workflow approachable.

### B — Chromium capture and Streamlit distribution ✅

The extension uses an explicitly enabled debugger session to observe Drive media
metadata and launch a browser download. Streamlit adds a visual tester plus an
extension ZIP/install guide, with Docker/devcontainer scaffolding for distribution.

### C — Authenticated Chrome-profile cookie support ✅

The latest release accepts exported Netscape cookies or a raw Cookie header and a
Drive account index so the CLI can reuse a browser session that already has access.
The README and helper batch file explain profile selection and cookie expiry. D
keeps the benefit while narrowing the credential and transfer risks.

### D — Credential-safe, integrity-aware single download ▶

**Value shipped:** an authorized user can start, interrupt, and resume one large
video; the tool either atomically produces a verified final file or leaves an
honest resumable partial with a specific recovery message. Cookies and signed URLs
do not escape their necessary hosts or appear in output/logs.

**Riskiest assumption:** users will rely on this tool for meaningful files once it
can prove resume safety and explain access/processing/network/file failures.

The release includes:

1. Define an authorized-use, credential, media-identity, partial-file, conflict,
   retry, and completion contract with stable CLI statuses/exit codes.
2. Extract shared Drive ID, cookie/session, metadata discovery, URL validation,
   filename, transfer, resume, and redaction modules; keep CLI interaction thin.
3. Load only valid/scoped cookies, minimize which requests receive them, validate
   every redirect/media host, and redact cookie paths, values, headers, and signed
   URL queries—even in verbose/error output.
4. Write to `.part`, persist non-secret resume validators, require a matching `206`
   before append, handle ignored Range/unknown length/validated `416`, and promote
   only after content and byte-count checks.
5. Distinguish invalid ID, authentication, authorization, still-processing,
   non-video, expired playback URL, throttling, transient network, disk, conflict,
   and integrity failures without claiming the tool bypasses access control.
6. Prove the downloader against a local HTTP fault server plus sanitized Drive
   fixtures and a manual maintainer-owned public/private test file. No real cookie
   or signed URL enters the repository or CI logs.
7. Normalize requirements/configuration, introduce tests/CI/changelog, and make
   repository security/documentation match the actual behavior.

**Protected cut line:** credential scoping/redaction, allowlisted redirects, safe
resume, partial/final lifecycle, integrity/content checks, structured outcomes,
fault-injection tests, and truthful authorized-use documentation ship together.
UI work, extension refactors, quality choice, batch, subtitles, and richer metadata
are cut first if the 14-day ceiling is threatened.

**Not in D:** Streamlit private downloads, extension permission changes, multiple
quality selection, batch/parallel transfers, subtitles, public API, cloud storage,
or automatic cookie extraction from a browser profile.

### E — Least-privilege in-browser capture ⬜

**Value shipped:** an authorized user can capture and download a rendition from the
active Drive tab with a short-lived, visibly active debugger session and no broad
retention of response bodies or signed URLs.

Likely scope is explicit per-tab activation, Drive/media-specific host permissions,
deterministic attach/detach/cleanup, minimal response parsing, short-lived rendition
metadata, background-owned download initiation, explicit quality labels, and
permission/privacy disclosure. If current browser policy cannot support that
boundary, the extension is not distributed as a general-purpose release.

**Assumption retired:** the extension can deliver enough convenience while keeping
its powerful debugger permission narrow, understandable, and reviewable.

### F — Bounded local GUI for non-CLI users ⬜

**Value shipped:** a non-CLI user can run the same safe transfer core locally,
choose an authorized file and cookie source, see progress/recovery state, and save
to disk without uploading credentials or video bytes to a public host.

Candidate scope is a local-only Streamlit adapter around D's core, bounded temp/
partial handling, explicit cookie warnings, cancellation/resume, correct extension
packaging, and one documented environment. The hosted page may remain a static
install guide, but it does not proxy private video bodies.

**Assumption retired:** a GUI meaningfully broadens safe use beyond users who can
run the CLI.

### G — Rendition choice and small authorized queue ⬜

**Value shipped:** a user can choose an available, explicitly labeled rendition
and process a small ordered list of authorized videos with independent outcomes and
resume state.

Candidate scope is normalized rendition metadata, deterministic quality/default
selection, bounded sequential concurrency, per-item output/conflict/retry status,
and a queue manifest containing no cookies or signed URLs. Parallelism, subtitles,
and large unattended jobs remain outside the initial slice.

**Assumption retired:** quality choice and queueing save enough repeated work to
justify the additional expiring-URL, rate-limit, disk, and recovery complexity.

---

## Definition of done for every release

A milestone is shipped only when:

- Its end-to-end benefit works on a maintainer-owned/authorized fixture from a
  clean supported environment.
- Unit, parser, cookie/redaction, redirect, HTTP fault, resume, filesystem,
  extension, and packaging tests pass where applicable.
- No real cookie, authorization header, signed URL, private title, or video body is
  present in source, fixtures, snapshots, logs, CI artifacts, or release evidence.
- Interrupted and resumed test files match the expected final bytes/hash; ignored
  Range, unknown length, changed validators, redirects, `416`, and disk errors do
  not yield false success.
- Permissions and credential use are no broader or longer-lived than the shipped
  benefit requires.
- `README.md`, `CONTRIBUTING.md`, `TASKS.md`, this roadmap, dependency/config files,
  privacy/authorized-use language, and changelog/version evidence agree.
- A commit or release identifier and verification evidence are recorded in the
  milestone table; completion requires proof, not intent.

---

## Retrospective and re-plan cadence

Run a checkpoint after each release, or after seven maintainer-days without a
release, whichever comes first.

At each checkpoint:

1. Review corrupted/mismatched files, resume restarts, auth/access failures,
   expired URLs, credential exposure, extension permission friction, memory/disk
   usage, and capacity spent.
2. Decide whether the release's risky assumption was supported, contradicted, or
   still untested.
3. Re-cut the remaining scope inside the fixed eight-week/40-day frame. Detail
   only the next milestone and leave later releases coarse.
4. Update the milestone table, evidence, capacity remaining, and review date in
   both roadmap files.

Any credential leak, unapproved host request, corrupt “success,” or private-video
proxy path interrupts feature work immediately. The correction replaces planned
scope; the deadline and capacity do not move.

---

## Explicitly parked

These are not part of the eight-week frame without new evidence and a new roadmap:

- Downloading content the user cannot already access or is not authorized to save.
- Automatic browser-profile database access, password/decryption extraction, or
  background cookie harvesting.
- A hosted proxy for private video, shared cookie upload, accounts, analytics, or
  retained download history.
- Parallel/unbounded batch jobs, distributed workers, cloud destinations, or a
  public download API.
- DRM circumvention, access-control exploits, or guarantees about platform policy/
  terms/legal permission.
- Video conversion, transcoding, compression, editing, or media-library features.
