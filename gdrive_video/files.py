"""Conflict-safe filename, sidecar, partial, and atomic-promotion behavior."""

from __future__ import annotations

import json
import mimetypes
import os
import stat
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import GDriveVideoError
from .models import FailureKind

SIDECAR_SCHEMA = 1
MAX_SIDECAR_BYTES = 16 * 1024
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
INVALID_FILENAME_CHARS = frozenset('<>:"/\\|?*')


@dataclass(frozen=True, slots=True)
class OutputPlan:
    final: Path
    partial: Path
    sidecar: Path


@dataclass(slots=True)
class ResumeState:
    schema_version: int
    source_id: str
    expected_total: int | None
    etag: str | None
    last_modified: str | None
    content_type: str
    expected_sha256: str | None
    completed_bytes: int


def _filesystem_error(message: str) -> GDriveVideoError:
    return GDriveVideoError(FailureKind.FILESYSTEM, message)


def sanitize_filename(value: str, source_id: str) -> str:
    """Return a non-empty cross-platform-safe basename."""

    normalized = unicodedata.normalize("NFKC", value or "")
    cleaned = (
        "".join(
            "_" if char in INVALID_FILENAME_CHARS or ord(char) < 32 or ord(char) == 127 else char
            for char in normalized
        )
        .strip()
        .rstrip(" .")
    )
    if not cleaned:
        cleaned = f"drive-{source_id}"
    stem = cleaned.split(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    while len(cleaned.encode("utf-8")) > 180:
        cleaned = cleaned[:-1].rstrip(" .")
    return cleaned or f"drive-{source_id}"


def extension_for(content_type: str | None) -> str:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    known = {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "video/x-msvideo": ".avi",
        "video/mpeg": ".mpeg",
    }
    if media_type in known:
        return known[media_type]
    guessed = mimetypes.guess_extension(media_type) if media_type.startswith("video/") else None
    return guessed or ".mp4"


def _lstat_or_none(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise _filesystem_error("An output path could not be inspected safely.") from None


def _reject_symlink_or_special(path: Path, *, allow_regular: bool) -> None:
    metadata = _lstat_or_none(path)
    if metadata is None:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise GDriveVideoError(FailureKind.CONFLICT, "A symlink exists at a protected output path.")
    if not allow_regular or not stat.S_ISREG(metadata.st_mode):
        raise GDriveVideoError(
            FailureKind.CONFLICT, "A non-regular entry exists at an output path."
        )


def _reject_symlinked_ancestors(path: Path) -> None:
    """Reject any existing symlink component between a path and its anchor."""

    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        metadata = _lstat_or_none(candidate)
        if metadata is not None and stat.S_ISLNK(metadata.st_mode):
            raise GDriveVideoError(
                FailureKind.CONFLICT,
                "A symlinked output directory component was refused.",
            )


def plan_output(
    *,
    output: Path | None,
    title: str | None,
    source_id: str,
    content_type: str | None,
    overwrite: bool,
) -> OutputPlan:
    """Resolve final/partial paths without creating or truncating anything."""

    generated = sanitize_filename(title or "", source_id)
    if not Path(generated).suffix:
        generated += extension_for(content_type)

    if output is None:
        final = Path.cwd() / generated
    else:
        requested = Path(output).expanduser()
        if requested.exists() and requested.is_dir():
            final = requested / generated
        else:
            basename = sanitize_filename(requested.name, source_id)
            if not Path(basename).suffix:
                basename += extension_for(content_type)
            final = requested.parent / basename

    parent = final.parent
    _reject_symlinked_ancestors(parent)
    parent_meta = _lstat_or_none(parent)
    if parent_meta is not None and stat.S_ISLNK(parent_meta.st_mode):
        raise GDriveVideoError(FailureKind.CONFLICT, "A symlinked output directory was refused.")
    if parent_meta is None or not stat.S_ISDIR(parent_meta.st_mode):
        raise GDriveVideoError(FailureKind.CONFLICT, "The output directory does not exist.")

    final_meta = _lstat_or_none(final)
    if final_meta is not None:
        if stat.S_ISLNK(final_meta.st_mode) or not stat.S_ISREG(final_meta.st_mode):
            raise GDriveVideoError(
                FailureKind.CONFLICT,
                "A symlink or non-regular entry exists at the final output path.",
            )
        if not overwrite:
            raise GDriveVideoError(
                FailureKind.CONFLICT,
                "The final output already exists; choose another path or explicitly "
                "use --overwrite.",
            )

    partial = Path(f"{final}.part")
    sidecar = Path(f"{final}.part.json")
    _reject_symlink_or_special(partial, allow_regular=True)
    _reject_symlink_or_special(sidecar, allow_regular=True)
    return OutputPlan(final=final, partial=partial, sidecar=sidecar)


def _read_sidecar(path: Path, expected: os.stat_result) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            current = os.fstat(handle.fileno())
            if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
                raise GDriveVideoError(
                    FailureKind.CONFLICT,
                    "The resume sidecar changed while it was being opened.",
                )
            raw = handle.read(MAX_SIDECAR_BYTES + 1)
            if len(raw) > MAX_SIDECAR_BYTES:
                raise GDriveVideoError(
                    FailureKind.CONFLICT,
                    "The resume sidecar grew beyond its safety limit.",
                )
    except GDriveVideoError:
        raise
    except OSError:
        raise GDriveVideoError(
            FailureKind.CONFLICT,
            "The resume sidecar could not be read safely.",
        ) from None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise GDriveVideoError(
            FailureKind.CONFLICT,
            "The resume sidecar is not valid UTF-8.",
        ) from None


def load_resume_state(plan: OutputPlan, source_id: str) -> ResumeState | None:
    """Load a matching non-secret sidecar and reconcile crash-lagged byte count."""

    partial_meta = _lstat_or_none(plan.partial)
    sidecar_meta = _lstat_or_none(plan.sidecar)
    if partial_meta is None and sidecar_meta is None:
        return None
    if partial_meta is None or sidecar_meta is None:
        raise GDriveVideoError(
            FailureKind.CONFLICT,
            "A stale partial or sidecar was found; preserve it or use --restart to archive it.",
        )
    _reject_symlink_or_special(plan.partial, allow_regular=True)
    _reject_symlink_or_special(plan.sidecar, allow_regular=True)
    if sidecar_meta.st_size <= 0 or sidecar_meta.st_size > MAX_SIDECAR_BYTES:
        raise GDriveVideoError(FailureKind.CONFLICT, "The resume sidecar is empty or oversized.")
    try:
        payload = json.loads(_read_sidecar(plan.sidecar, sidecar_meta))
    except json.JSONDecodeError:
        raise GDriveVideoError(
            FailureKind.CONFLICT, "The resume sidecar is unreadable or malformed."
        ) from None
    allowed = {
        "schema_version",
        "source_id",
        "expected_total",
        "etag",
        "last_modified",
        "content_type",
        "expected_sha256",
        "completed_bytes",
    }
    if not isinstance(payload, dict) or set(payload) != allowed:
        raise GDriveVideoError(FailureKind.CONFLICT, "The resume sidecar schema is invalid.")
    try:
        state = ResumeState(**payload)
    except TypeError:
        raise GDriveVideoError(
            FailureKind.CONFLICT, "The resume sidecar schema is invalid."
        ) from None
    if (
        not isinstance(state.schema_version, int)
        or isinstance(state.schema_version, bool)
        or state.schema_version != SIDECAR_SCHEMA
        or not isinstance(state.source_id, str)
        or state.source_id != source_id
    ):
        raise GDriveVideoError(
            FailureKind.CONFLICT, "The partial belongs to a different source or schema."
        )
    if (
        not isinstance(state.completed_bytes, int)
        or isinstance(state.completed_bytes, bool)
        or state.completed_bytes < 0
        or (
            state.expected_total is not None
            and (
                not isinstance(state.expected_total, int)
                or isinstance(state.expected_total, bool)
                or state.expected_total < 0
            )
        )
        or not isinstance(state.content_type, str)
        or not state.content_type.startswith("video/")
        or (state.etag is not None and (not isinstance(state.etag, str) or len(state.etag) > 1024))
        or (
            state.last_modified is not None
            and (not isinstance(state.last_modified, str) or len(state.last_modified) > 1024)
        )
        or (
            state.expected_sha256 is not None
            and (
                not isinstance(state.expected_sha256, str)
                or len(state.expected_sha256) != 64
                or any(char not in "0123456789abcdef" for char in state.expected_sha256)
            )
        )
    ):
        raise GDriveVideoError(FailureKind.CONFLICT, "The resume sidecar values are invalid.")
    for validator in (state.etag, state.last_modified):
        if validator is not None and any(ord(char) < 32 or ord(char) == 127 for char in validator):
            raise GDriveVideoError(
                FailureKind.CONFLICT,
                "The resume sidecar contains an invalid source validator.",
            )
    actual_size = partial_meta.st_size
    if state.completed_bytes > actual_size:
        raise GDriveVideoError(
            FailureKind.CONFLICT, "The partial is shorter than its recorded resume state."
        )
    if state.expected_total is not None and actual_size > state.expected_total:
        raise GDriveVideoError(
            FailureKind.CONFLICT, "The partial is larger than its expected remote total."
        )
    state.completed_bytes = actual_size
    return state


def write_resume_state(path: Path, state: ResumeState) -> None:
    """Atomically persist a small mode-0600 sidecar in the output directory."""

    payload = json.dumps(asdict(state), sort_keys=True, separators=(",", ":")) + "\n"
    descriptor = -1
    temporary = ""
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
    except OSError:
        raise _filesystem_error("The resume sidecar could not be persisted.") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def archive_partial(plan: OutputPlan) -> tuple[Path, ...]:
    """Move old partial artifacts to conflict-free names without deleting them."""

    existing = [path for path in (plan.partial, plan.sidecar) if _lstat_or_none(path) is not None]
    if not existing:
        return ()
    suffix = 1
    while True:
        targets = tuple(Path(f"{path}.stale.{suffix}") for path in existing)
        if all(_lstat_or_none(path) is None for path in targets):
            break
        suffix += 1
    moved: list[Path] = []
    try:
        for source, target in zip(existing, targets, strict=True):
            os.replace(source, target)
            moved.append(target)
    except OSError:
        raise _filesystem_error("Old partial artifacts could not be archived safely.") from None
    return tuple(moved)


def promote_partial(plan: OutputPlan, *, overwrite: bool) -> bool:
    """Atomically expose a complete partial, preserving no-overwrite semantics."""

    try:
        if overwrite:
            _reject_symlink_or_special(plan.final, allow_regular=True)
            os.replace(plan.partial, plan.final)
        else:
            os.link(plan.partial, plan.final, follow_symlinks=False)
            try:
                os.unlink(plan.partial)
            except OSError:
                try:
                    os.unlink(plan.final)
                except OSError:
                    raise _filesystem_error(
                        "Atomic promotion cleanup failed; both a valid final and "
                        "partial may exist.",
                    ) from None
                raise _filesystem_error(
                    "Atomic promotion could not remove the partial; the final link "
                    "was rolled back.",
                ) from None
    except FileExistsError:
        raise GDriveVideoError(
            FailureKind.CONFLICT,
            "The final output appeared during transfer and was not overwritten.",
        ) from None
    except OSError:
        raise _filesystem_error(
            "Atomic final-file promotion failed; the partial was preserved."
        ) from None
    try:
        plan.sidecar.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        # The final is already valid and visible. Report success with a cleanup
        # warning rather than claim the transfer failed after promotion.
        return False
    return True
