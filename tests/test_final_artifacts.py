import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = PROJECT_ROOT / "demo" / "evidence" / "final" / "final-transfer-transcript.txt"
SERVER_LOG = PROJECT_ROOT / "demo" / "evidence" / "final" / "final-server.log"
REPORT = PROJECT_ROOT / "docs" / "technical-report.md"


class FinalArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([sys.executable, str(PROJECT_ROOT / "demo" / "final_submission_demo.py")], cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def test_final_evidence_has_transfer_hash_and_session_output(self):
        transcript = TRANSCRIPT.read_text(encoding="utf-8")
        log = SERVER_LOG.read_text(encoding="utf-8")
        for required in ["150 Opening UDP data connection", "226 Transfer complete", "SHA-256 local=", "match=True", "active_sessions=1", "Final submission demo complete"]:
            self.assertIn(required, transcript)
        for required in ["rdt send", "rdt ack", "rdt window", "transfer complete"]:
            self.assertIn(required, log)
        for secret in ["cs494", "hybridftp-final-"]:
            self.assertNotIn(secret, transcript)
            self.assertNotIn(secret, log)

    def test_report_covers_all_mandatory_sections(self):
        report = REPORT.read_text(encoding="utf-8")
        for heading in [
            "## 1. Application Scenario & Protocol Interaction",
            "## 2. Project-Wide Data Structures",
            "## 3. Functional Workflows",
            "## 4. Task Assignment Matrix",
            "## 5. Self-Assessment & Peer Evaluation",
            "## 6. GenAI Usage & Code Refinement Log",
            "## 7. Application Demo Evidence",
            "Phan Tan Dat",
            "23125030",
        ]:
            self.assertIn(heading, report)


if __name__ == "__main__":
    unittest.main()
