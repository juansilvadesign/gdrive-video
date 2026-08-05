# Tasks

The living implementation checklist. Strategy, release boundaries, and the fixed
frame live in **[`ROADMAP.md`](ROADMAP.md)**.

_Last reviewed: 2026-08-05_

> Milestones **A–C** are shipped. **D is the only execution-ready milestone.**
> Items under E–G are deliberately coarse and must be re-planned after the
> preceding retrospective.

---

## Next — Milestone D: credential-safe, integrity-aware single download ▶

**Capacity ceiling:** 14 maintainer-days.

**Exit outcome:** an authorized CLI download either produces an atomically
completed, content-checked file or a truthful resumable `.part`; no cookie, signed
URL, or authorization detail leaks or crosses an unverified host.

### 0. Start the fixed frame safely

- [ ] Record the implementation kickoff date and resulting eight-week end date in
      [`ROADMAP.md`](ROADMAP.md#fixed-frame); keep the 40-day total and D's 14-day
      ceiling fixed.
- [ ] Capture a clean git baseline and record the starting commit in D's release
      notes. Preserve unrelated work if the tree is not clean.
- [ ] Inventory tracked/ignored secret-like files and repository history without
      printing values. Classify `.streamlit/secrets.toml`; remove it if unused,
      replace it with a non-secret example if needed, and rotate/revoke anything
      that is actually sensitive before feature work continues.
- [ ] Create maintainer-owned Drive fixtures with known bytes/hash: one public
      video, one private video shared to a test account, one still-processing/non-
      video case where practical, and no third-party copyrighted content.
- [ ] Create sanitized metadata fixtures and synthetic cookies/signed URLs that
      preserve parser shape but contain no usable credential.
- [ ] Record current behavior for fresh, interrupted, ignored-Range, missing-length,
      changed-file, `416`, timeout, bad-cookie, and disk-full simulations.

### 1. Lock authorization, transfer, and status contracts

- [ ] Replace “bypass/protected/any video” product language with a precise contract:
      the user must already be able and authorized to access/save the file.
- [ ] Define accepted Drive URL/ID forms and reject ambiguous text instead of
      extracting an arbitrary ID-like substring.
- [ ] Define a media identity using stable non-secret fields such as file ID plus
      validated size/ETag/Last-Modified/content identity when available.
- [ ] Define `.part`, resume sidecar, final-file, overwrite/conflict, stale-part,
      and cleanup behavior before changing filesystem code.
- [ ] Define retryable versus terminal failures and stable outcomes/CLI exit codes
      for invalid input, authentication, authorization, processing, non-video,
      expired playback URL, throttling, network, disk, conflict, cancellation, and
      integrity errors.
- [ ] Define separate connect/read timeouts, bounded retries/backoff, and
      `Retry-After` behavior; an active large transfer must not use one ambiguous
      30-second timeout policy.
- [ ] Define what completion proves: accepted media response, expected range,
      expected byte count when known, optional digest, flushed/closed file, and
      atomic final promotion.

### 2. Extract one tested download core

- [ ] Split pure Drive ID parsing, cookie parsing/scoping, redaction, metadata
      discovery, response validation, filename planning, resume state, and transfer
      decisions from prompts/progress rendering.
- [ ] Make `main.py` a thin CLI adapter around typed/documented request, progress,
      and result objects; no deep helper should print directly.
- [ ] Centralize URL/host validation and secret redaction so verbose, errors, tests,
      and future Streamlit/extension adapters cannot bypass them.
- [ ] Parse Drive metadata with structured query/form parsing and bounded decoding,
      not `split("&")`/`split("=")[-1]` heuristics.
- [ ] Preserve signed playback URLs only in short-lived memory needed for transfer;
      never place them in resume metadata or exception text.
- [ ] Validate title/filename separately from media identity and provide a safe
      non-empty fallback based on the Drive file ID.
- [ ] Close responses/sessions deterministically on success, failure, cancellation,
      and retry.

### 3. Contain cookies and signed URLs

- [ ] Prefer cookie formats that retain domain/path/secure/expiry metadata. Decide
      whether raw `Cookie:` files can be made acceptably scoped; otherwise
      deprecate/reject them with a migration message.
- [ ] Do not load expired cookies by default. Report expired/missing/empty/malformed
      jars without naming cookie values.
- [ ] Validate cookie-file type, ownership/permissions where the OS exposes them,
      symlink/size boundaries, and regular-file status before reading.
- [ ] Attach only the minimum cookies to the exact Google hosts that require them;
      never create domainless cookies that ride every request in the session.
- [ ] Characterize which metadata/media requests actually require cookies using
      owned fixtures, then strip them from all other hosts.
- [ ] Revalidate every redirect hop for HTTPS and the measured Drive/media host
      allowlist; refuse downgrades, credential-bearing URLs, userinfo, unknown
      hosts, and excessive redirect chains.
- [ ] Redact signed query values, cookie paths, account/session hints, headers, and
      response snippets from normal/verbose logs and exceptions.
- [ ] Add a startup warning that exported cookies are temporary login credentials,
      plus actionable deletion/expiry guidance that never deletes user files
      automatically.
- [ ] Ensure synthetic credentials used in tests are unmistakably nonfunctional and
      add a repository/CI secret scan before release.

### 4. Make resume and finalization correct

- [ ] Validate `chunk_size` as a bounded positive integer before any request or
      filesystem mutation.
- [ ] Resolve output safely across reserved names, control characters, trailing
      dots/spaces, empty sanitized titles, explicit directories, collisions,
      symlinks, and existing final/partial files.
- [ ] Download only to `<name>.part` and store a non-secret sidecar with source ID,
      expected total/validators, completed bytes, and schema version.
- [ ] For a resume, send `Range` plus `If-Range` when a valid validator exists and
      append only after a `206` whose `Content-Range` starts at the local byte count
      and whose total/validator matches the sidecar.
- [ ] If the server returns `200` to a Range request, never append. Choose and
      document a safe restart/new-file action without losing the old partial
      silently.
- [ ] For `416`, parse and compare the remote total with local bytes/identity before
      declaring complete; otherwise mark the partial stale or corrupt.
- [ ] When length is unknown, stream until clean EOF and finish without inventing a
      total; preserve an indeterminate progress state.
- [ ] Reject login/error HTML, JSON error bodies, implausible content types, empty
      bodies, and unexpected content encodings before promoting a file as video.
- [ ] Handle signed-URL expiry during transfer by rediscovering metadata and
      resuming only if media identity still matches.
- [ ] Flush, optionally `fsync` according to the chosen durability contract, close,
      verify known size/digest, then atomically rename `.part` to the conflict-safe
      final path.
- [ ] On Ctrl+C, timeout, retry exhaustion, or disk error, preserve a consistent
      partial/sidecar and print one redacted recovery command/status.

### 5. Build the HTTP fault and filesystem regression matrix

- [ ] Add a local test server that can emit fresh `200`, correct/malformed `206`,
      ignored Range `200`, valid/invalid `416`, known/unknown length, changed ETag,
      redirects, partial disconnects, stalls, 403/404/429/5xx, and HTML errors.
- [ ] Prove fresh and every valid resume path produce byte-for-byte/hash-identical
      output to the fixture source.
- [ ] Prove ignored Range, wrong start/total, changed validators/content, invalid
      `416`, and unexpected hosts never append or promote.
- [ ] Prove unknown-length transfers stream to EOF rather than report an empty file
      complete.
- [ ] Test transient retry/backoff and `Retry-After` deterministically without real
      sleeps or external network.
- [ ] Test connect/read timeouts, cancellation, permission denied, disk full/write
      failure, atomic-rename failure, stale sidecar, symlink, collision, and
      existing-final behavior.
- [ ] Test strict ID/URL parsing, encoded metadata delimiters, missing/multiple
      titles/streams, oversized metadata, and safe title fallback.
- [ ] Test Netscape/raw-cookie decisions, expiry/domain/path/secure scoping,
      redirect stripping, and redaction across stdout, logs, exceptions, snapshots,
      sidecars, and CI artifacts.
- [ ] Keep CI offline: sanitized fixtures and the local server cover behavior; live
      Drive checks remain explicit manual release evidence.

### 6. Normalize repository and release hygiene

- [ ] Convert `requirements.txt` from UTF-16 to a standard UTF-8 dependency format,
      separate runtime/development requirements, and verify clean installation.
- [ ] Determine the supported Python range from CI evidence and align README,
      Docker, devcontainer, type syntax, and dependency constraints.
- [ ] Choose one virtual-environment name/workflow across `run.bat`,
      `streamlit.bat`, docs, and contributor instructions; do not install on every
      ordinary launch.
- [ ] Add formatter/lint/type checks proportionate to the codebase plus a test
      command and CI workflow.
- [ ] Run a current dependency/license/security audit and add valid automated
      dependency update configuration.
- [ ] Remove unsafe development defaults such as disabling XSRF protection; keep
      local exceptions explicit and non-production.
- [ ] Document that Streamlit/extension remain legacy surfaces until E/F and ensure
      D does not accidentally claim their safety contract.

### 7. Accept and release D

- [ ] Run the full offline fault/filesystem/credential suite on every supported OS
      and Python version.
- [ ] Download the maintainer-owned public fixture fresh, interrupt it, resume it,
      and compare the final size/hash to the source.
- [ ] Repeat with the authorized private fixture and an exported test-account cookie
      jar; inspect captured logs/traffic to prove cookie and redirect scoping.
- [ ] Exercise expired/wrong-account cookies, processing/non-video content, signed-
      URL expiry, unknown length where reproducible, conflict, and Ctrl+C recovery.
- [ ] Verify no usable credential, signed URL, private title, or response body is
      present in git status/history additions, test artifacts, logs, sidecars, or
      release notes.
- [ ] Rewrite `README.md` around authorized use, real surface status, credential
      handling, safe resume, recovery, limitations, and executable setup commands;
      remove unsupported time-bound/bypass guarantees.
- [ ] Expand `CONTRIBUTING.md` with fixtures, secret hygiene, tests, and release
      evidence requirements.
- [ ] Add `CHANGELOG.md` and record resume/partial-file, cookie format/scoping,
      logging, filename, error, and compatibility changes.
- [ ] Bump/version the CLI only after automated and manual evidence is green.
- [ ] Record the release commit/tag and evidence in [`ROADMAP.md`](ROADMAP.md), mark
      D shipped, and re-plan E inside the remaining capacity.

---

## Later — Milestone E: least-privilege in-browser capture ⬜

Do not expand these items until D proves credential/redaction/integrity semantics.

- [ ] Reassess the browser extension against current Chromium extension/debugger/
      store policies before implementation or distribution.
- [ ] Replace one global enabled flag with explicit per-tab, user-gesture activation
      limited to an active Drive tab.
- [ ] Reduce host permissions to the measured Drive/media hosts and explain the
      unavoidable power of `debugger` before attachment.
- [ ] Make attach/detach idempotent and race-safe across reload, navigation, tab
      close, service-worker suspension, errors, and OFF.
- [ ] Parse only required metadata, discard response bodies immediately, keep signed
      URLs short-lived in the background, and send only safe rendition metadata to
      the popup.
- [ ] Select/display renditions by explicit metadata rather than array position and
      initiate downloads through the narrowest component.
- [ ] Add mocked Chrome API/event lifecycle tests, filename tests, accessible popup
      states, privacy disclosure, and package/review evidence.

---

## Later — Milestone F: bounded local GUI for non-CLI users ⬜

- [ ] Remove/disable the public private-video proxy path; decide whether the hosted
      surface becomes a static install guide or is retired.
- [ ] Rebuild Streamlit as a local adapter around D's discovery/transfer core with
      streamed disk-backed partials, progress, cancellation, resume, and limits.
- [ ] Keep cookies local, never upload them to a hosted instance, and show the same
      credential warnings/redacted outcomes as CLI.
- [ ] Bound memory, disk, request lifetime, temp cleanup, and concurrent sessions;
      never use `response.content` for large video bodies.
- [ ] Fix Docker/package inclusion for every downloadable asset and use one
      reproducible environment/configuration.
- [ ] Test keyboard, focus, screen-reader, error/recovery, large-file, multi-session,
      restart, and cleanup behavior.

---

## Later — Milestone G: rendition choice and small authorized queue ⬜

- [ ] Validate real demand and available rendition metadata before committing to
      quality labels or queueing.
- [ ] Normalize codec/container/resolution/bitrate/size fields and make the default
      deterministic without assuming array order means quality.
- [ ] Add a bounded ordered queue with per-item auth, discovery, partial, retry,
      conflict, completion, and cancellation state.
- [ ] Store no cookies or signed URLs in queue manifests; refresh expiring URLs only
      through the credential-safe session.
- [ ] Start sequentially; add concurrency only after measured rate-limit, memory,
      disk, and integrity evidence supports it.

---

## Completed — Milestone C: authenticated cookie support ✅

- [x] Accept Drive URLs plus a Google account index.
- [x] Load exported Netscape cookies or a raw Cookie header into a Requests session.
- [x] Add a Windows helper for selecting a Drive link, cookie file, and account.
- [x] Ignore common cookie-export filenames and document browser-profile selection,
      export, expiry, and handling warnings.
- [x] Ship cookie support in `5e85a2e`.

---

## Completed — Milestone B: extension and Streamlit surfaces ✅

- [x] Add a Manifest V3 Chromium extension that captures Drive video metadata via
      the debugger/network APIs and triggers browser downloads.
- [x] Add popup enable/disable, polling, captured-video list, and filename cleanup.
- [x] Add a Streamlit landing/tester surface with extension ZIP download and manual
      installation guidance.
- [x] Add Docker, Compose, Streamlit configuration, devcontainer, and launch script
      scaffolding.
- [x] Ship the extension in `df34565`, Streamlit in `8942d4b`, and the extension ZIP
      repair in `6cf1b17`.

---

## Completed — Milestone A: interactive/resumable CLI ✅

- [x] Accept a Drive video ID or common URL forms in interactive/argument modes.
- [x] Discover a playback URL and title, choose an output name/extension, and stream
      with a TQDM progress bar.
- [x] Attempt Range-based continuation when an output file already exists.
- [x] Support custom output, chunk size, verbose mode, version/help, and Windows
      batch launch.
- [x] Document installation and example commands.

---

## Parked — not committed in the current frame

- Content the user cannot already access or is not authorized to download.
- Browser-profile database/decryption access or background cookie harvesting.
- Hosted private-video proxying, cookie uploads, accounts, analytics, or history.
- Parallel/unbounded batch, cloud destinations, or a public download API.
- DRM/access-control circumvention or policy/legal guarantees.
- Transcoding, conversion, compression, editing, or media-library management.
