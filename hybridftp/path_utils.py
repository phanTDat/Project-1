"""Server-root sandbox helpers for present and future filesystem commands."""

from __future__ import annotations

from pathlib import Path


def resolve_server_root(root: Path) -> Path:
    """Create and return an absolute resolved server root path."""

    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def ensure_within_root(root: Path, candidate: Path) -> Path:
    """Resolve candidate and reject paths outside root."""

    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate == resolved_root or resolved_root in resolved_candidate.parents:
        return resolved_candidate
    raise ValueError(f"path escapes server root: {candidate}")
