"""Generate deterministic Phase 2 filesystem command demo evidence."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hybridftp.client import connect_and_run
from hybridftp.server import start_test_server

EVIDENCE_DIR = PROJECT_ROOT / "demo" / "evidence" / "phase2"
TRANSCRIPT_PATH = EVIDENCE_DIR / "phase2-filesystem-transcript.txt"
SERVER_LOG_PATH = EVIDENCE_DIR / "phase2-server.log"
DEMO_ROOT = EVIDENCE_DIR / "server_root_runtime"
DEMO_PASSWORD = "cs494"

COMMANDS = [
    "USER student",
    f"PASS {DEMO_PASSWORD}",
    "PWD",
    "CWD docs",
    "PWD",
    "CDUP",
    "LIST /",
    "NLST /",
    "STAT",
    "STAT /",
    "SIZE /docs/readme.txt",
    "MDTM /docs/readme.txt",
    "SIZE /docs",
    "MKD created",
    "RMD empty",
    "DELE docs",
    "DELE ../outside.txt",
    "RNTO no-source.txt",
    "RNFR old.txt",
    "RNTO existing.txt",
    "RNTO second-try.txt",
    "RNFR old.txt",
    "RNTO renamed.txt",
    "DELE delete-me.txt",
    "RMD /",
    "RNFR /",
    "RMD nested",
    "LIST /name with space.txt",
    "QUIT",
]

EXPECTED_TRANSCRIPT = [
    "220 Hybrid FTP server ready",
    "331 User name okay, need password",
    "230 User logged in",
    "ftp> PASS <redacted>",
    '257 "/" is current directory',
    '250 Directory changed to "/docs"',
    '257 "/docs" is current directory',
    "212-",
    "212 End",
    "dir entries=",
    "name with space.txt",
    "cwd=/ root=/",
    "213 15",
    '257 "/created" created',
    "350 Requested file action pending further information",
    "503 Bad sequence of commands",
    "550",
    "250 Requested file action okay, completed",
    "221 Goodbye",
]


def _prepare_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir()
    (root / "empty").mkdir()
    (root / "nested" / "child").mkdir(parents=True)
    (root / "docs" / "readme.txt").write_text("hello phase two", encoding="utf-8")
    (root / "delete-me.txt").write_text("delete", encoding="utf-8")
    (root / "old.txt").write_text("old", encoding="utf-8")
    (root / "existing.txt").write_text("existing", encoding="utf-8")
    (root / "name with space.txt").write_text("space", encoding="utf-8")
    (root / ".hidden").write_text("hidden", encoding="utf-8")


def _require_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected transcript/log to contain: {needle!r}")


def _require_absent(text: str, needle: str) -> None:
    if needle in text:
        raise AssertionError(f"sensitive or unstable raw value leaked into evidence: {needle!r}")


def _redact(text: str, root: Path) -> str:
    text = text.replace("PASS ********", "PASS <redacted>")
    text = text.replace(str(root.resolve()), "<server_root>")
    text = text.replace(str(root), "<server_root>")
    text = text.replace(str(DEMO_ROOT.resolve()), "<server_root>")
    text = text.replace(str(DEMO_ROOT), "<server_root>")
    text = text.replace(DEMO_PASSWORD, "<redacted-password>")
    return text


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_PATH.write_text("", encoding="utf-8")
    SERVER_LOG_PATH.write_text("", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="phase2-server-root-") as tmp:
        run_root = Path(tmp) / "server_root_runtime"
        _prepare_root(run_root)

        server = start_test_server(root=run_root, log_file=SERVER_LOG_PATH)
        transcript_buffer = io.StringIO()
        try:
            connect_and_run(server.host, server.port, commands=COMMANDS, transcript=transcript_buffer)
        finally:
            server.stop()
            server.join()

        transcript = _redact(transcript_buffer.getvalue(), run_root) + "Phase 2 demo complete\n"
        server_log = _redact(SERVER_LOG_PATH.read_text(encoding="utf-8"), run_root)

    for expected in EXPECTED_TRANSCRIPT:
        _require_contains(transcript, expected)
    for command in ["PWD", "CWD", "CDUP", "MKD", "RMD", "LIST", "NLST", "STAT", "SIZE", "MDTM", "DELE", "RNFR", "RNTO"]:
        _require_contains(transcript, f"ftp> {command}")
    for safety in ["ftp> DELE docs", "ftp> DELE ../outside.txt", "ftp> RMD /", "ftp> RNTO no-source.txt", "ftp> RNTO existing.txt"]:
        _require_contains(transcript, safety)
    for expected in ["session=", "client=", "command=", "reply=", "virtual=/", "PASS <redacted>"]:
        _require_contains(server_log, expected)
    for secret in [DEMO_PASSWORD, str(DEMO_ROOT.resolve()), str(DEMO_ROOT)]:
        _require_absent(transcript, secret)
        _require_absent(server_log, secret)

    TRANSCRIPT_PATH.write_text(transcript, encoding="utf-8")
    SERVER_LOG_PATH.write_text(server_log, encoding="utf-8")
    print("Phase 2 demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
