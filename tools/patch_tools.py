"""Safe patch proposal and inspection tools for VEGA."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.safety import (
    FileSafetyError,
    get_project_root,
    validate_writable_text_file,
)


MAX_PATCH_CHARS = 200_000
PATCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _result(data: Any = None, error: str | None = None) -> dict:
    return {
        "ok": error is None,
        "error": error,
        "data": data if error is None else None,
    }


def _relative(path: Path) -> str:
    return path.resolve().relative_to(get_project_root().resolve()).as_posix()


def _patch_paths() -> dict[str, Path]:
    root = get_project_root() / "data" / "patches"

    paths = {
        "root": root,
        "pending": root / "pending",
        "applied": root / "applied",
        "backups": root / "backups",
        "history": root / "history.json",
    }

    paths["pending"].mkdir(parents=True, exist_ok=True)
    paths["applied"].mkdir(parents=True, exist_ok=True)
    paths["backups"].mkdir(parents=True, exist_ok=True)

    if not paths["history"].exists():
        _write_json_atomic(paths["history"], [])

    return paths


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_newline(text: str) -> str:
    crlf_count = text.count("\r\n")
    remaining = text.replace("\r\n", "")
    lf_count = remaining.count("\n")
    cr_count = remaining.count("\r")

    counts = {
        "\r\n": crlf_count,
        "\n": lf_count,
        "\r": cr_count,
    }

    newline, count = max(counts.items(), key=lambda item: item[1])
    return newline if count > 0 else "\n"


def _newline_name(newline: str) -> str:
    return {
        "\r\n": "CRLF",
        "\n": "LF",
        "\r": "CR",
    }[newline]


def _normalize_newlines(text: str, newline: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", newline)


def _read_utf8_file(path: Path) -> tuple[bytes, str, bool, str]:
    raw = path.read_bytes()

    if len(raw) > MAX_PATCH_CHARS * 4 + 4:
        raise FileSafetyError(
            f"File is too large for Patch Tools: maximum {MAX_PATCH_CHARS} characters."
        )

    has_bom = raw.startswith(b"\xef\xbb\xbf")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileSafetyError(
            "Only valid UTF-8 text files can be used by Patch Tools."
        ) from exc

    if len(text) > MAX_PATCH_CHARS:
        raise FileSafetyError(
            f"File is too large for Patch Tools: maximum {MAX_PATCH_CHARS} characters."
        )

    newline = _detect_newline(text)
    return raw, text, has_bom, newline


def _encode_proposed_text(
    text: str,
    *,
    has_bom: bool,
    newline: str,
) -> tuple[str, bytes]:
    normalized = _normalize_newlines(text, newline)
    encoded = normalized.encode("utf-8")

    if has_bom:
        encoded = b"\xef\xbb\xbf" + encoded

    return normalized, encoded


def _build_diff(
    target_path: str,
    original_text: str,
    proposed_text: str,
) -> str:
    return "".join(
        difflib.unified_diff(
            original_text.splitlines(keepends=True),
            proposed_text.splitlines(keepends=True),
            fromfile=f"a/{target_path}",
            tofile=f"b/{target_path}",
            lineterm="\n",
        )
    )


def _new_patch_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"patch-{stamp}-{uuid.uuid4().hex[:8]}"


def _validate_patch_id(patch_id: str) -> str:
    if (
        not isinstance(patch_id, str)
        or not patch_id
        or not PATCH_ID_PATTERN.fullmatch(patch_id)
    ):
        raise FileSafetyError("Invalid patch ID.")

    return patch_id


def _find_patch_file(patch_id: str) -> Path:
    patch_id = _validate_patch_id(patch_id)
    paths = _patch_paths()

    for directory in (paths["pending"], paths["applied"]):
        candidate = directory / f"{patch_id}.json"
        if candidate.is_file():
            return candidate

    raise FileSafetyError(f"Patch does not exist: {patch_id}")


def propose_patch(
    target_path: str,
    new_content: str,
    reason: str = "",
) -> dict:
    """Prepare a pending patch without changing the target file."""
    try:
        if not isinstance(new_content, str):
            raise FileSafetyError("New content must be text.")

        if not new_content:
            raise FileSafetyError("New content must not be empty.")

        if len(new_content) > MAX_PATCH_CHARS:
            raise FileSafetyError(
                f"New content exceeds the limit of {MAX_PATCH_CHARS} characters."
            )

        target = validate_writable_text_file(target_path)
        relative_target = _relative(target)

        original_raw, original_text, has_bom, newline = _read_utf8_file(target)

        proposed_text, proposed_raw = _encode_proposed_text(
            new_content,
            has_bom=has_bom,
            newline=newline,
        )

        if original_raw == proposed_raw:
            raise FileSafetyError("Patch contains no changes.")

        diff = _build_diff(
            relative_target,
            original_text,
            proposed_text,
        )

        if not diff:
            raise FileSafetyError("Patch contains no visible text changes.")

        patch_id = _new_patch_id()
        created_at = datetime.now(timezone.utc).isoformat()

        metadata = {
            "patch_id": patch_id,
            "target_path": relative_target,
            "reason": reason.strip() if isinstance(reason, str) else "",
            "status": "pending",
            "created_at": created_at,
            "original_sha256": _sha256(original_raw),
            "proposed_sha256": _sha256(proposed_raw),
            "original_size": len(original_raw),
            "proposed_size": len(proposed_raw),
            "has_utf8_bom": has_bom,
            "newline": _newline_name(newline),
            "diff": diff,
            "new_content": proposed_text,
        }

        paths = _patch_paths()
        patch_file = paths["pending"] / f"{patch_id}.json"

        _write_json_atomic(patch_file, metadata)

        return _result({
            "patch_id": patch_id,
            "target_path": relative_target,
            "status": "pending",
            "reason": metadata["reason"],
            "original_sha256": metadata["original_sha256"],
            "proposed_sha256": metadata["proposed_sha256"],
            "diff": diff,
        })

    except (FileSafetyError, OSError, ValueError) as exc:
        return _result(error=str(exc))


def propose_patch_from_file(
    target_path: str,
    proposal_path: str,
    reason: str = "",
) -> dict:
    """Prepare a patch using another safe UTF-8 file as proposed content."""
    try:
        target = validate_writable_text_file(target_path)
        proposal = validate_writable_text_file(proposal_path)

        if target.resolve() == proposal.resolve():
            raise FileSafetyError(
                "Target file and proposal file must be different."
            )

        _, proposal_text, _, _ = _read_utf8_file(proposal)

        return propose_patch(
            target_path=target_path,
            new_content=proposal_text,
            reason=reason,
        )

    except (FileSafetyError, OSError, ValueError) as exc:
        return _result(error=str(exc))


def list_patches(status: str | None = None) -> dict:
    """List saved patches without returning their full contents."""
    try:
        allowed_statuses = {None, "pending", "applied", "rolled_back"}

        if status not in allowed_statuses:
            raise FileSafetyError(
                "Status must be pending, applied, rolled_back, or omitted."
            )

        paths = _patch_paths()
        items = []

        for directory in (paths["pending"], paths["applied"]):
            for patch_file in sorted(directory.glob("*.json")):
                try:
                    metadata = json.loads(
                        patch_file.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    continue

                patch_status = metadata.get("status")

                if status is not None and patch_status != status:
                    continue

                items.append({
                    "patch_id": metadata.get("patch_id"),
                    "target_path": metadata.get("target_path"),
                    "reason": metadata.get("reason", ""),
                    "status": patch_status,
                    "created_at": metadata.get("created_at"),
                })

        items.sort(
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )

        return _result(items)

    except (FileSafetyError, OSError, ValueError) as exc:
        return _result(error=str(exc))


def show_patch(patch_id: str) -> dict:
    """Return patch metadata and unified diff."""
    try:
        patch_file = _find_patch_file(patch_id)
        metadata = json.loads(patch_file.read_text(encoding="utf-8"))

        visible = {
            key: value
            for key, value in metadata.items()
            if key != "new_content"
        }

        return _result(visible)

    except (
        FileSafetyError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return _result(error=str(exc))


def _load_patch_metadata(patch_file: Path) -> dict:
    try:
        metadata = json.loads(patch_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FileSafetyError("Patch metadata is corrupted.") from exc

    if not isinstance(metadata, dict):
        raise FileSafetyError("Patch metadata must be a JSON object.")

    expected_id = patch_file.stem
    if metadata.get("patch_id") != expected_id:
        raise FileSafetyError("Patch metadata ID does not match its filename.")

    return metadata


def _newline_from_name(name: str) -> str:
    mapping = {
        "CRLF": "\r\n",
        "LF": "\n",
        "CR": "\r",
    }

    try:
        return mapping[name]
    except KeyError as exc:
        raise FileSafetyError("Patch contains an invalid newline format.") from exc


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _append_history(entry: dict) -> None:
    paths = _patch_paths()

    try:
        history = json.loads(
            paths["history"].read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise FileSafetyError("Patch history is corrupted.") from exc

    if not isinstance(history, list):
        raise FileSafetyError("Patch history must be a JSON list.")

    history.append(entry)
    _write_json_atomic(paths["history"], history)


def _proposed_bytes_from_metadata(metadata: dict) -> bytes:
    new_content = metadata.get("new_content")

    if not isinstance(new_content, str):
        raise FileSafetyError("Patch does not contain valid proposed content.")

    newline = _newline_from_name(metadata.get("newline"))
    has_bom = metadata.get("has_utf8_bom")

    if not isinstance(has_bom, bool):
        raise FileSafetyError("Patch contains an invalid BOM setting.")

    _, proposed_raw = _encode_proposed_text(
        new_content,
        has_bom=has_bom,
        newline=newline,
    )

    expected_hash = metadata.get("proposed_sha256")
    if _sha256(proposed_raw) != expected_hash:
        raise FileSafetyError(
            "Proposed patch content does not match its saved SHA-256."
        )

    return proposed_raw


def apply_patch(
    patch_id: str,
    confirmed: bool = False,
) -> dict:
    """Apply a pending patch only after explicit confirmation."""
    try:
        if confirmed is not True:
            raise FileSafetyError(
                "Patch application requires explicit confirmation."
            )

        patch_file = _find_patch_file(patch_id)
        paths = _patch_paths()

        if patch_file.resolve().parent != paths["pending"].resolve():
            raise FileSafetyError("Only pending patches can be applied.")

        metadata = _load_patch_metadata(patch_file)

        if metadata.get("status") != "pending":
            raise FileSafetyError("Only pending patches can be applied.")

        target_path = metadata.get("target_path")
        if not isinstance(target_path, str):
            raise FileSafetyError("Patch target path is invalid.")

        target = validate_writable_text_file(target_path)
        current_raw = target.read_bytes()

        if _sha256(current_raw) != metadata.get("original_sha256"):
            raise FileSafetyError(
                "Target file changed after the patch was proposed. "
                "The stale patch was not applied."
            )

        proposed_raw = _proposed_bytes_from_metadata(metadata)
        backup_file = paths["backups"] / f"{patch_id}.bak"

        if backup_file.exists():
            raise FileSafetyError(
                "Backup already exists for this patch."
            )

        applied_file = paths["applied"] / f"{patch_id}.json"
        _atomic_write_bytes(backup_file, current_raw)

        try:
            _atomic_write_bytes(target, proposed_raw)

            written_raw = target.read_bytes()
            if _sha256(written_raw) != metadata.get("proposed_sha256"):
                raise FileSafetyError(
                    "Written file failed SHA-256 verification."
                )

            applied_at = datetime.now(timezone.utc).isoformat()
            updated = dict(metadata)
            updated.update({
                "status": "applied",
                "applied_at": applied_at,
                "backup_path": _relative(backup_file),
            })

            _write_json_atomic(applied_file, updated)
            patch_file.unlink()

            _append_history({
                "patch_id": patch_id,
                "target_path": target_path,
                "action": "applied",
                "timestamp": applied_at,
            })

        except Exception:
            try:
                _atomic_write_bytes(target, current_raw)
            finally:
                if applied_file.exists():
                    applied_file.unlink()

                if not patch_file.exists():
                    _write_json_atomic(patch_file, metadata)

                if backup_file.exists():
                    backup_file.unlink()

            raise

        return _result({
            "patch_id": patch_id,
            "target_path": target_path,
            "status": "applied",
            "backup_path": _relative(backup_file),
            "sha256": metadata["proposed_sha256"],
        })

    except Exception as exc:
        return _result(error=str(exc))


def rollback_patch(
    patch_id: str,
    confirmed: bool = False,
) -> dict:
    """Restore an applied patch only after explicit confirmation."""
    try:
        if confirmed is not True:
            raise FileSafetyError(
                "Patch rollback requires explicit confirmation."
            )

        patch_file = _find_patch_file(patch_id)
        paths = _patch_paths()

        if patch_file.resolve().parent != paths["applied"].resolve():
            raise FileSafetyError("Only applied patches can be rolled back.")

        metadata = _load_patch_metadata(patch_file)

        if metadata.get("status") != "applied":
            raise FileSafetyError("Only applied patches can be rolled back.")

        target_path = metadata.get("target_path")
        if not isinstance(target_path, str):
            raise FileSafetyError("Patch target path is invalid.")

        target = validate_writable_text_file(target_path)
        current_raw = target.read_bytes()

        if _sha256(current_raw) != metadata.get("proposed_sha256"):
            raise FileSafetyError(
                "Target file changed after the patch was applied. "
                "Rollback was blocked to protect later user changes."
            )

        backup_value = metadata.get("backup_path")
        if not isinstance(backup_value, str):
            raise FileSafetyError("Patch backup path is invalid.")

        backup_file = get_project_root() / backup_value

        try:
            backup_file.resolve().relative_to(
                paths["backups"].resolve()
            )
        except ValueError as exc:
            raise FileSafetyError(
                "Patch backup is outside the backup directory."
            ) from exc

        if not backup_file.is_file():
            raise FileSafetyError("Patch backup does not exist.")

        original_raw = backup_file.read_bytes()

        if _sha256(original_raw) != metadata.get("original_sha256"):
            raise FileSafetyError(
                "Patch backup failed SHA-256 verification."
            )

        proposed_raw = _proposed_bytes_from_metadata(metadata)
        original_metadata = dict(metadata)

        try:
            _atomic_write_bytes(target, original_raw)

            restored_raw = target.read_bytes()
            if _sha256(restored_raw) != metadata.get("original_sha256"):
                raise FileSafetyError(
                    "Restored file failed SHA-256 verification."
                )

            rolled_back_at = datetime.now(timezone.utc).isoformat()
            updated = dict(metadata)
            updated.update({
                "status": "rolled_back",
                "rolled_back_at": rolled_back_at,
            })

            _write_json_atomic(patch_file, updated)

            _append_history({
                "patch_id": patch_id,
                "target_path": target_path,
                "action": "rolled_back",
                "timestamp": rolled_back_at,
            })

        except Exception:
            try:
                _atomic_write_bytes(target, proposed_raw)
                _write_json_atomic(patch_file, original_metadata)
            finally:
                pass

            raise

        return _result({
            "patch_id": patch_id,
            "target_path": target_path,
            "status": "rolled_back",
            "sha256": metadata["original_sha256"],
        })

    except Exception as exc:
        return _result(error=str(exc))
