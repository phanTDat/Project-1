import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = PROJECT_ROOT / "demo" / "evidence" / "phase2" / "phase2-filesystem-transcript.txt"
SERVER_LOG = PROJECT_ROOT / "demo" / "evidence" / "phase2" / "phase2-server.log"


class Phase2ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "demo" / "phase2_filesystem_demo.py")],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)

    def test_curated_phase2_evidence_is_present_redacted_and_complete(self):
        transcript = TRANSCRIPT.read_text(encoding="utf-8")
        server_log = SERVER_LOG.read_text(encoding="utf-8")
        for needle in [
            "220 Hybrid FTP server ready",
            "230 User logged in",
            "257",
            "250 Requested file action okay, completed",
            "212-",
            "212 End",
            "213",
            "350 Requested file action pending further information",
            "503 Bad sequence of commands",
            "550",
            "221 Goodbye",
            "Phase 2 demo complete",
        ]:
            self.assertIn(needle, transcript)
        for command in ["PWD", "CWD", "CDUP", "MKD", "RMD", "LIST", "NLST", "STAT", "SIZE", "MDTM", "DELE", "RNFR", "RNTO"]:
            self.assertIn(f"ftp> {command}", transcript)
        for needle in [
            "name with space.txt",
            "/docs",
            "cwd=/ root=/",
            "ftp> DELE docs",
            "ftp> DELE ../outside.txt",
            "ftp> RMD /",
            "ftp> RNTO no-source.txt",
            "ftp> RNTO existing.txt",
            "PASS <redacted>",
        ]:
            self.assertIn(needle, transcript)
        for needle in ["session=", "client=", "command=", "reply=", "virtual=/"]:
            self.assertIn(needle, server_log)
        self.assertIn("PASS <redacted>", server_log)
        forbidden = ["cs494", "phase2-server-root-", "server_root_runtime", "server root=D:", "server root=C:"]
        for secret in forbidden:
            self.assertNotIn(secret, transcript)
            self.assertNotIn(secret, server_log)

    def test_phase2_evidence_remains_a_filesystem_slice(self):
        transcript = TRANSCRIPT.read_text(encoding="utf-8")
        self.assertIn("Phase 2 demo complete", transcript)
        self.assertIn("ftp> LIST", transcript)


if __name__ == "__main__":
    unittest.main()
