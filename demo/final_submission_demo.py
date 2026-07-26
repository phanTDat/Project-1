"""Generate curated Excellent-level Hybrid FTP final demo evidence."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hybridftp.client import connect_and_run
from hybridftp.integrity import sha256_path
from hybridftp.server import start_test_server

EVIDENCE_DIR = PROJECT_ROOT / "demo" / "evidence" / "final"
TRANSCRIPT = EVIDENCE_DIR / "final-transfer-transcript.txt"
SERVER_LOG = EVIDENCE_DIR / "final-server.log"


def redact(text: str, root: Path) -> str:
    return text.replace("PASS ********", "PASS <redacted>").replace(str(root.resolve()), "<server_root>").replace("cs494", "<redacted-password>")


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT.write_text("", encoding="utf-8")
    SERVER_LOG.write_text("", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="hybridftp-final-") as tmp:
        root = Path(tmp) / "server"
        local = Path(tmp) / "binary-fixture.bin"
        downloaded = Path(tmp) / "downloaded.bin"
        local.write_bytes(bytes(range(256)) * 16 + b"Hybrid FTP final binary fixture\x00")
        server = start_test_server(root, SERVER_LOG)
        transcript = io.StringIO()
        try:
            connect_and_run(
                server.host,
                server.port,
                commands=[
                    "USER student",
                    "PASS cs494",
                    "TYPE I",
                    "MODE S",
                    f"put {local} evidence.bin",
                    f"get evidence.bin {downloaded}",
                    "STAT",
                    "QUIT",
                ],
                transcript=transcript,
            )
        finally:
            server.stop()
            server.join()
        if sha256_path(local) != sha256_path(downloaded):
            raise AssertionError("binary evidence hash mismatch")
        text = redact(transcript.getvalue(), root)
        log = redact(SERVER_LOG.read_text(encoding="utf-8"), root)
    for required in ["150 Opening UDP data connection", "226 Transfer complete", "SHA-256 local=", "match=True", "active_sessions=1", "221 Goodbye"]:
        if required not in text:
            raise AssertionError(f"missing final evidence: {required}")
    for required in ["rdt send", "rdt ack", "rdt window", "transfer complete"]:
        if required not in log:
            raise AssertionError(f"missing server log evidence: {required}")
    TRANSCRIPT.write_text(text + "Final submission demo complete\n", encoding="utf-8")
    SERVER_LOG.write_text(log, encoding="utf-8")
    print("Final submission demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
