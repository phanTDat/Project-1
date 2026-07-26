"""Safe server-root filesystem helpers for Hybrid FTP Phase 2 commands."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .path_utils import ensure_within_root
from .session import Session


class FilesystemError(ValueError):
    """Safe filesystem failure with an FTP reply code and educational text."""

    def __init__(self, message: str, code: int = 550) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ResolvedPath:
    virtual: PurePosixPath
    real: Path


def virtual_to_text(path: PurePosixPath) -> str:
    text = path.as_posix()
    return text if text.startswith("/") else f"/{text}"


def _has_control_character(text: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def clean_argument(argument: str, *, required: bool) -> str:
    text = argument.strip()
    if required and not text:
        raise FilesystemError("Syntax error in parameters or arguments", 501)
    if "\x00" in text or _has_control_character(text):
        raise FilesystemError("Unsafe path argument")
    if "\\" in text:
        raise FilesystemError("Backslashes are not valid FTP path separators")
    return text


def normalize_virtual_path(argument: str, cwd: PurePosixPath, *, required: bool = True) -> PurePosixPath:
    text = clean_argument(argument, required=required)
    if not text:
        return cwd
    parts: list[str] = []
    source = PurePosixPath(text) if text.startswith("/") else cwd.joinpath(text)
    for part in source.parts:
        if part in ("", "/", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            else:
                raise FilesystemError("Path escapes server root")
        else:
            parts.append(part)
    return PurePosixPath("/", *parts)


def resolve_virtual_path(session: Session, argument: str, *, required: bool = True, must_exist: bool = False) -> ResolvedPath:
    virtual = normalize_virtual_path(argument, session.cwd, required=required)
    real = session.server_root.joinpath(*virtual.parts[1:])
    try:
        resolved = real.resolve(strict=must_exist)
        if not must_exist and not real.exists():
            resolved = ensure_within_root(session.server_root, real)
        else:
            resolved = ensure_within_root(session.server_root, resolved)
    except (OSError, ValueError) as exc:
        raise FilesystemError("Path is outside the server root") from exc
    if _contains_link_escape(session.server_root, real):
        raise FilesystemError("Unsafe link target rejected")
    return ResolvedPath(virtual=virtual, real=resolved)


def _contains_link_escape(root: Path, candidate: Path) -> bool:
    root = root.resolve()
    current = root
    relative_parts = candidate.relative_to(root).parts if candidate.is_absolute() else candidate.parts
    for part in relative_parts:
        current = current / part
        try:
            if current.is_symlink():
                target = current.resolve()
                if target != root and root not in target.parents:
                    return True
            if hasattr(os.stat_result, "st_file_attributes") and current.exists():
                stat = current.stat()
                attrs = getattr(stat, "st_file_attributes", 0)
                if attrs & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                    target = current.resolve()
                    if target != root and root not in target.parents:
                        return True
        except OSError:
            return False
    return False


def real_to_virtual(root: Path, real: Path) -> PurePosixPath:
    resolved_root = root.resolve()
    resolved_real = ensure_within_root(resolved_root, real)
    if resolved_real == resolved_root:
        return PurePosixPath("/")
    return PurePosixPath("/", *resolved_real.relative_to(resolved_root).parts)


def timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y%m%d%H%M%S")


def metadata_line(root: Path, virtual: PurePosixPath, real: Path) -> str:
    name = "/" if virtual == PurePosixPath("/") else virtual.name
    if real.is_dir():
        count = sum(1 for _ in real.iterdir())
        return f"dir entries={count} mtime={timestamp(real)} path={virtual_to_text(virtual)} name={name}"
    return f"file size={real.stat().st_size} mtime={timestamp(real)} path={virtual_to_text(virtual)} name={name}"


def _sorted_children(path: Path) -> list[Path]:
    children = list(path.iterdir())
    return sorted(children, key=lambda p: (not p.is_dir(), p.name.lower(), p.name))


def list_detailed(session: Session, argument: str = "") -> tuple[PurePosixPath, list[str]]:
    target = resolve_virtual_path(session, argument, required=False, must_exist=True)
    if target.real.is_file():
        return target.virtual, [metadata_line(session.server_root, target.virtual, target.real)]
    if not target.real.is_dir():
        raise FilesystemError("Target is not listable")
    lines = []
    for child in _sorted_children(target.real):
        child_virtual = target.virtual.joinpath(child.name) if target.virtual != PurePosixPath("/") else PurePosixPath("/", child.name)
        lines.append(metadata_line(session.server_root, child_virtual, child))
    return target.virtual, lines


def list_names(session: Session, argument: str = "") -> tuple[PurePosixPath, list[str]]:
    target = resolve_virtual_path(session, argument, required=False, must_exist=True)
    if target.real.is_file():
        return target.virtual, [target.real.name]
    if not target.real.is_dir():
        raise FilesystemError("Target is not listable")
    return target.virtual, [child.name for child in _sorted_children(target.real)]


def change_directory(session: Session, argument: str) -> PurePosixPath:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    if not target.real.is_dir():
        raise FilesystemError("Target is not a directory")
    session.cwd = target.virtual
    return target.virtual


def change_to_parent(session: Session) -> PurePosixPath:
    if session.cwd == PurePosixPath("/"):
        return session.cwd
    parent = session.cwd.parent
    target = resolve_virtual_path(session, virtual_to_text(parent), required=True, must_exist=True)
    if not target.real.is_dir():
        raise FilesystemError("Current directory parent is unavailable")
    session.cwd = target.virtual
    return session.cwd


def make_directory(session: Session, argument: str) -> PurePosixPath:
    target = resolve_virtual_path(session, argument, required=True, must_exist=False)
    if target.virtual == PurePosixPath("/") or target.real.exists():
        raise FilesystemError("Directory already exists or target is invalid")
    if not target.real.parent.exists() or not target.real.parent.is_dir():
        raise FilesystemError("Parent directory does not exist")
    target.real.mkdir()
    return target.virtual


def _is_cwd_or_parent(session: Session, virtual: PurePosixPath) -> bool:
    cwd = session.cwd
    return virtual == cwd or virtual in cwd.parents


def remove_directory(session: Session, argument: str) -> PurePosixPath:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    if target.virtual == PurePosixPath("/") or _is_cwd_or_parent(session, target.virtual):
        raise FilesystemError("Cannot remove the current directory, its parent, or root")
    if not target.real.is_dir():
        raise FilesystemError("Target is not an empty directory")
    try:
        target.real.rmdir()
    except OSError as exc:
        raise FilesystemError("Directory not empty") from exc
    return target.virtual


def delete_file(session: Session, argument: str) -> PurePosixPath:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    if target.virtual == PurePosixPath("/") or not target.real.is_file():
        raise FilesystemError("Target is not a regular file")
    target.real.unlink()
    return target.virtual


def file_size(session: Session, argument: str) -> int:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    if not target.real.is_file():
        raise FilesystemError("SIZE requires a regular file")
    return target.real.stat().st_size


def modified_time(session: Session, argument: str) -> str:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    return timestamp(target.real)


def stat_path(session: Session, argument: str) -> tuple[PurePosixPath, str]:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    return target.virtual, metadata_line(session.server_root, target.virtual, target.real)


def rename_from(session: Session, argument: str) -> PurePosixPath:
    target = resolve_virtual_path(session, argument, required=True, must_exist=True)
    if target.virtual == PurePosixPath("/") or _is_cwd_or_parent(session, target.virtual):
        raise FilesystemError("Cannot rename root, current directory, or its parent")
    session.rename_from_real = target.real
    session.rename_from_virtual = target.virtual
    return target.virtual


def rename_to(session: Session, argument: str) -> PurePosixPath:
    source_real = session.rename_from_real
    source_virtual = session.rename_from_virtual
    session.rename_from_real = None
    session.rename_from_virtual = None
    if source_real is None or source_virtual is None:
        raise FilesystemError("Bad sequence of commands", 503)
    target = resolve_virtual_path(session, argument, required=True, must_exist=False)
    if target.real.exists():
        raise FilesystemError("Destination already exists")
    if not target.real.parent.exists() or not target.real.parent.is_dir():
        raise FilesystemError("Destination parent does not exist")
    if source_real.is_dir():
        try:
            if source_real.resolve() == target.real.resolve() or source_real.resolve() in target.real.resolve().parents:
                raise FilesystemError("Cannot move a directory into its own descendant")
        except OSError as exc:
            raise FilesystemError("Unsafe rename destination") from exc
    source_real.rename(target.real)
    return target.virtual
