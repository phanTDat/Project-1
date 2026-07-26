import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase1ArtifactTests(unittest.TestCase):
    def test_readme_and_genai_log_cover_phase1_handoff_requirements(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        for needle in [
            "py -3 -m hybridftp.server",
            "py -3 -m hybridftp.client",
            "--no-connect",
            "put <local-file>",
            "get <remote-file>",
            "py -3 server.py",
            "py -3 client.py",
            "student",
            "cs494",
            "py -3 -m unittest discover -s tests -v",
            "py -3 demo/phase1_control_demo.py",
        ]:
            self.assertIn(needle, readme)
        self.assertIn("TCP only for control", readme)
        self.assertIn("custom reliable UDP protocol", readme)
        self.assertIn("Demo credentials", readme)

        genai_log = (PROJECT_ROOT / "docs" / "genai-usage-log.md").read_text(encoding="utf-8")
        for heading in [
            "Prompt",
            "Raw AI Output Summary",
            "Human Refinement and Verification",
            "Accepted Refinements",
            "Student Critical Analysis and Refinements",
            "Planned Verification",
            "2026-06-04",
        ]:
            self.assertIn(heading, genai_log)

    def test_curated_phase1_evidence_is_present_and_redacted(self):
        transcript = (PROJECT_ROOT / "demo" / "evidence" / "phase1" / "phase1-control-transcript.txt").read_text(
            encoding="utf-8"
        )
        server_log = (PROJECT_ROOT / "demo" / "evidence" / "phase1" / "phase1-server.log").read_text(
            encoding="utf-8"
        )
        for needle in [
            "220 Hybrid FTP server ready",
            "530 Invalid username",
            "503 Bad sequence of commands",
            "530 Not logged in",
            "530 Login incorrect",
            "331 User name okay, need password",
            "230 User logged in",
            "214-",
            "200 NOOP ok",
            "500 Unknown command",
            "502 Command not implemented yet",
            "221 Goodbye",
            "ftp> PASS ********",
            "Phase 1 demo complete",
        ]:
            self.assertIn(needle, transcript)
        for needle in ["session=", "client=", "connect", "command=", "reply=", "authenticated", "quit", "disconnect"]:
            self.assertIn(needle, server_log)
        self.assertIn("PASS ********", server_log)
        for secret in ["anything", "wrong", "cs494"]:
            self.assertNotIn(secret, transcript)
            self.assertNotIn(secret, server_log)

    def test_phase1_source_avoids_banned_ftp_transfer_libraries(self):
        banned = ["ftplib", "pyftpdlib", "kcp", "quic", "libcurl"]
        source_paths = [
            PROJECT_ROOT / "hybridftp" / "server.py",
            PROJECT_ROOT / "hybridftp" / "client.py",
            PROJECT_ROOT / "server.py",
            PROJECT_ROOT / "client.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_paths)
        for token in banned:
            self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
