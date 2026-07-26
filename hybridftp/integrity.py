"""Streaming SHA-256 helpers for byte-preserving Hybrid FTP transfers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class HashComparison:
    """A local/server digest comparison suitable for client output."""

    local: str
    remote: str

    @property
    def matches(self) -> bool:
        return self.local.lower() == self.remote.lower()


def sha256_stream(stream: BinaryIO) -> str:
    """Return a SHA-256 digest while reading the stream in bounded chunks."""

    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK_SIZE):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    """Return the SHA-256 digest of a regular file without loading it into memory."""

    with path.open("rb") as stream:
        return sha256_stream(stream)
