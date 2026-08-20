from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from conftest import ETAG, LAST_MODIFIED, SOURCE_ID

from gdrive_video.errors import GDriveVideoError
from gdrive_video.files import (
    SIDECAR_SCHEMA,
    OutputPlan,
    ResumeState,
    archive_partial,
    load_resume_state,
    plan_output,
    promote_partial,
    sanitize_filename,
    write_resume_state,
)


def state(*, completed: int = 3, total: int | None = 10) -> ResumeState:
    return ResumeState(
        schema_version=SIDECAR_SCHEMA,
        source_id=SOURCE_ID,
        expected_total=total,
        etag=ETAG,
        last_modified=LAST_MODIFIED,
        content_type="video/mp4",
        expected_sha256=None,
        completed_bytes=completed,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", f"drive-{SOURCE_ID}"),
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("name. ", "name"),
        ('a/b\\c:*?"<>|', "a_b_c_______"),
        ("control\x00name", "control_name"),
    ],
)
def test_filename_sanitization_is_cross_platform_safe(raw: str, expected: str) -> None:
    assert sanitize_filename(raw, SOURCE_ID) == expected


def test_filename_is_utf8_bounded_and_unknown_type_uses_mp4(tmp_path: Path) -> None:
    name = sanitize_filename("é" * 200, SOURCE_ID)
    assert 0 < len(name.encode("utf-8")) <= 180
    plan = plan_output(
        output=tmp_path / "no-extension",
        title=None,
        source_id=SOURCE_ID,
        content_type="application/octet-stream",
        overwrite=False,
    )
    assert plan.final.suffix == ".mp4"


def test_output_planning_supports_explicit_directory_and_safe_fallback(tmp_path: Path) -> None:
    plan = plan_output(
        output=tmp_path,
        title=None,
        source_id=SOURCE_ID,
        content_type="video/webm",
        overwrite=False,
    )
    assert plan.final == tmp_path / f"drive-{SOURCE_ID}.webm"
    assert plan.partial == Path(f"{plan.final}.part")
    assert plan.sidecar == Path(f"{plan.final}.part.json")


def test_custom_output_keeps_directory_but_sanitizes_basename(tmp_path: Path) -> None:
    plan = plan_output(
        output=tmp_path / "bad:name. ",
        title="ignored",
        source_id=SOURCE_ID,
        content_type="video/mp4",
        overwrite=False,
    )
    assert plan.final == tmp_path / "bad_name.mp4"


def test_missing_or_non_directory_parent_is_a_conflict(tmp_path: Path) -> None:
    with pytest.raises(GDriveVideoError, match="does not exist"):
        plan_output(
            output=tmp_path / "missing" / "video.mp4",
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=False,
        )
    parent_file = tmp_path / "parent-file"
    parent_file.write_bytes(b"x")
    with pytest.raises(GDriveVideoError, match="does not exist"):
        plan_output(
            output=parent_file / "video.mp4",
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=False,
        )


def test_existing_final_requires_explicit_overwrite(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    final.write_bytes(b"old")
    with pytest.raises(GDriveVideoError, match="already exists"):
        plan_output(
            output=final,
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=False,
        )
    assert (
        plan_output(
            output=final,
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=True,
        ).final
        == final
    )


def test_symlinks_are_rejected_for_final_partial_sidecar_and_parent(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"x")
    final = tmp_path / "video.mp4"
    final.symlink_to(target)
    with pytest.raises(GDriveVideoError, match="symlink"):
        plan_output(
            output=final,
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=True,
        )

    final.unlink()
    partial = Path(f"{final}.part")
    partial.symlink_to(target)
    with pytest.raises(GDriveVideoError, match="symlink"):
        plan_output(
            output=final,
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=False,
        )

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    linked_dir = tmp_path / "linked"
    linked_dir.symlink_to(real_dir, target_is_directory=True)
    with pytest.raises(GDriveVideoError, match="symlinked output directory"):
        plan_output(
            output=linked_dir / "video.mp4",
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=False,
        )

    nested = linked_dir / "nested" / "video.mp4"
    (real_dir / "nested").mkdir()
    with pytest.raises(GDriveVideoError, match="component"):
        plan_output(
            output=nested,
            title=None,
            source_id=SOURCE_ID,
            content_type="video/mp4",
            overwrite=False,
        )


def test_sidecar_roundtrip_is_private_nonsecret_and_crash_lag_tolerant(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"abcdef")
    write_resume_state(plan.sidecar, state(completed=3, total=10))
    loaded = load_resume_state(plan, SOURCE_ID)
    assert loaded is not None
    assert loaded.completed_bytes == 6
    assert stat.S_IMODE(plan.sidecar.stat().st_mode) == 0o600
    payload = plan.sidecar.read_text(encoding="utf-8")
    assert "http" not in payload
    assert "title" not in payload
    assert "cookie" not in payload.lower()


def test_stale_or_mismatched_sidecar_is_rejected(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"abc")
    with pytest.raises(GDriveVideoError, match="stale"):
        load_resume_state(plan, SOURCE_ID)

    write_resume_state(plan.sidecar, state())
    payload = json.loads(plan.sidecar.read_text())
    payload["source_id"] = "B" * 25
    plan.sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(GDriveVideoError, match="different source"):
        load_resume_state(plan, SOURCE_ID)

    plan.partial.unlink()
    with pytest.raises(GDriveVideoError, match="stale"):
        load_resume_state(plan, SOURCE_ID)


@pytest.mark.parametrize(
    "raw",
    [b"", b"not-json", b"\xff", b"x" * (16 * 1024 + 1)],
)
def test_empty_malformed_non_utf8_or_oversized_sidecar_is_rejected(
    tmp_path: Path, raw: bytes
) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"abc")
    plan.sidecar.write_bytes(raw)
    with pytest.raises(GDriveVideoError):
        load_resume_state(plan, SOURCE_ID)


def test_sidecar_rejects_unknown_keys_and_oversized_partial(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"x" * 11)
    payload = (
        state().__dict__
        if hasattr(state(), "__dict__")
        else {
            "schema_version": 1,
            "source_id": SOURCE_ID,
            "expected_total": 10,
            "etag": ETAG,
            "last_modified": LAST_MODIFIED,
            "content_type": "video/mp4",
            "expected_sha256": None,
            "completed_bytes": 3,
        }
    )
    plan.sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(GDriveVideoError, match="larger"):
        load_resume_state(plan, SOURCE_ID)
    payload["signed_url"] = "https://example.invalid/?secret=UNUSABLE"
    plan.partial.write_bytes(b"abc")
    plan.sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(GDriveVideoError, match="schema"):
        load_resume_state(plan, SOURCE_ID)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("etag", '"ok"\nInjected: value'),
        ("last_modified", "value\rInjected"),
    ],
)
def test_sidecar_rejects_type_confusion_and_header_injection(
    tmp_path: Path, field: str, value: object
) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"abc")
    write_resume_state(plan.sidecar, state())
    payload = json.loads(plan.sidecar.read_text())
    payload[field] = value
    plan.sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(GDriveVideoError):
        load_resume_state(plan, SOURCE_ID)


def test_restart_archives_both_artifacts_without_overwrite(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"abc")
    write_resume_state(plan.sidecar, state())
    first = archive_partial(plan)
    assert len(first) == 2
    assert all(path.exists() for path in first)
    plan.partial.write_bytes(b"new")
    write_resume_state(plan.sidecar, state())
    second = archive_partial(plan)
    assert set(first).isdisjoint(second)
    assert all(path.exists() for path in second)


def test_archive_without_partial_state_is_a_noop(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    assert archive_partial(plan) == ()


def test_atomic_promotion_does_not_replace_unless_explicit(tmp_path: Path) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"new")
    write_resume_state(plan.sidecar, state(completed=3, total=3))
    final.write_bytes(b"old")
    with pytest.raises(GDriveVideoError, match="appeared"):
        promote_partial(plan, overwrite=False)
    assert final.read_bytes() == b"old"
    assert plan.partial.read_bytes() == b"new"

    promote_partial(plan, overwrite=True)
    assert final.read_bytes() == b"new"
    assert not plan.partial.exists()
    assert not plan.sidecar.exists()


def test_atomic_promotion_failure_preserves_partial(tmp_path: Path, monkeypatch) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"new")
    write_resume_state(plan.sidecar, state(completed=3, total=3))

    def fail_link(*_args, **_kwargs):
        raise OSError("synthetic no-link filesystem")

    monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(GDriveVideoError, match="promotion"):
        promote_partial(plan, overwrite=False)
    assert plan.partial.read_bytes() == b"new"
    assert plan.sidecar.exists()
    assert not final.exists()


def test_atomic_promotion_rolls_back_final_link_if_partial_unlink_fails(
    tmp_path: Path, monkeypatch
) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"new")
    write_resume_state(plan.sidecar, state(completed=3, total=3))
    real_unlink = os.unlink

    def fail_partial_unlink(path, *args, **kwargs):
        if Path(path) == plan.partial:
            raise OSError("synthetic unlink failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", fail_partial_unlink)
    with pytest.raises(GDriveVideoError, match="rolled back"):
        promote_partial(plan, overwrite=False)
    assert plan.partial.exists()
    assert plan.sidecar.exists()
    assert not final.exists()


def test_sidecar_cleanup_failure_returns_successful_promotion_warning(
    tmp_path: Path, monkeypatch
) -> None:
    final = tmp_path / "video.mp4"
    plan = OutputPlan(final, Path(f"{final}.part"), Path(f"{final}.part.json"))
    plan.partial.write_bytes(b"new")
    write_resume_state(plan.sidecar, state(completed=3, total=3))
    real_unlink = Path.unlink

    def fail_sidecar_unlink(path: Path, *args, **kwargs):
        if path == plan.sidecar:
            raise OSError("synthetic sidecar cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_sidecar_unlink)
    assert promote_partial(plan, overwrite=False) is False
    assert final.read_bytes() == b"new"
    assert not plan.partial.exists()
    assert plan.sidecar.exists()
